"""
AegisLab AI — Core AI Inference Engine (Multi-Key Resilient Fallback)
Cascading fallback: Gemini Key 1 → Gemini Key 2 → OpenAI Key 1 → OpenAI Key 2.
"""

import json
import logging

import google.generativeai as genai
from openai import AsyncOpenAI

from models.lab_data import ClinicalReportOutput, LabTestInput
from shared.config import settings

logger = logging.getLogger(__name__)


class AegisAnalyzer:
    """
    Wraps Google Gemini and OpenAI to perform clinical laboratory-result
    analysis and return structured JSON reports.

    **Resilience strategy**: Tries each configured API key in sequence.
    Gemini keys are tried first, then OpenAI keys. If all fail, raises
    RuntimeError with details of every failure.
    """

    SYSTEM_PROMPT: str = (
        "You are **AegisLab AI**, an advanced clinical laboratory diagnosis copilot.\n\n"
        "## Your Mission\n"
        "Analyze the provided laboratory test results and produce a comprehensive\n"
        "diagnostic assessment. You MUST respond with **valid JSON only** — no\n"
        "markdown fences, no commentary outside of the JSON object.\n\n"
        "## Output Schema (follow EXACTLY)\n"
        "```\n"
        "{\n"
        '  "summary": "<High-level natural-language summary of the lab results>",\n'
        '  "abnormal_values": ["<test name: value (reference range)>", ...],\n'
        '  "possible_conditions": [\n'
        '    {"name": "<condition>", "confidence_percentage": <0-100>}\n'
        "  ],\n"
        '  "risk_level": "<LOW | MODERATE | HIGH | CRITICAL>",\n'
        '  "explanation": "<Detailed clinical reasoning>",\n'
        '  "recommended_actions": ["<action>", ...],\n'
        '  "alerts": ["<urgent finding>", ...]\n'
        "}\n"
        "```\n\n"
        "## Rules\n"
        "1. Compare every value against standard medical reference ranges.\n"
        "2. Flag ALL abnormal values (high or low) with their reference range.\n"
        "3. List possible conditions ranked by likelihood (highest first).\n"
        "4. Set `risk_level` to exactly one of: LOW, MODERATE, HIGH, CRITICAL.\n"
        "5. Provide actionable, evidence-based recommended actions.\n"
        "6. Populate `alerts` only for values that are critically abnormal or\n"
        "   life-threatening; use an empty list if none.\n"
        "7. Be thorough, precise, and clinically accurate.\n"
        "8. NEVER fabricate lab values — only analyze what is provided.\n"
    )

    def __init__(self) -> None:
        """Configure all available API keys."""
        self.gemini_keys = settings.gemini_keys
        self.openai_keys = settings.openai_keys

        total = len(self.gemini_keys) + len(self.openai_keys)
        logger.info(
            "AegisAnalyzer initialized with %d Gemini key(s) and %d OpenAI key(s) — %d total fallback slots",
            len(self.gemini_keys),
            len(self.openai_keys),
            total,
        )

        if total == 0:
            logger.error("⚠ NO API KEYS CONFIGURED — analysis will fail!")

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_lab_tests(tests: dict) -> str:
        """Convert the tests dictionary into a human-readable string."""
        lines = [f"  • {name}: {value}" for name, value in tests.items()]
        return "\n".join(lines)

    @staticmethod
    def _parse_and_validate(raw_json: str, source: str) -> ClinicalReportOutput:
        """Parse raw JSON text and validate against ClinicalReportOutput."""
        try:
            parsed = json.loads(raw_json)
            report = ClinicalReportOutput(**parsed)
            logger.info(
                "Analysis complete via %s — risk_level=%s, conditions=%d",
                source,
                report.risk_level,
                len(report.possible_conditions),
            )
            return report
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "Failed to parse %s response as JSON: %s", source, exc, exc_info=True
            )
            raise ValueError(f"Invalid JSON from {source}: {exc}") from exc
        except Exception as exc:
            logger.error(
                "Pydantic validation failed for %s response: %s",
                source,
                exc,
                exc_info=True,
            )
            raise ValueError(f"{source} response validation failed: {exc}") from exc

    # ── Gemini attempt ───────────────────────────────────────────────────

    async def _try_gemini(self, api_key: str, prompt: str, label: str) -> ClinicalReportOutput:
        """Attempt analysis using a single Gemini API key."""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        logger.info("Trying %s …", label)

        response = await model.generate_content_async(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
            },
        )

        raw_text = response.text
        logger.debug("Raw %s response: %s", label, raw_text[:500])
        return self._parse_and_validate(raw_text, label)

    # ── OpenAI attempt ───────────────────────────────────────────────────

    async def _try_openai(self, api_key: str, user_message: str, label: str) -> ClinicalReportOutput:
        """Attempt analysis using a single OpenAI API key."""
        client = AsyncOpenAI(api_key=api_key)

        logger.info("Trying %s …", label)

        oai_response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )

        raw_text = oai_response.choices[0].message.content
        logger.debug("Raw %s response: %s", label, raw_text[:500])
        return self._parse_and_validate(raw_text, label)

    # ── public API ───────────────────────────────────────────────────────

    async def analyze_lab_results(
        self, lab_data: LabTestInput
    ) -> ClinicalReportOutput:
        """
        Send lab results for AI analysis with multi-key cascading fallback.

        Flow: Gemini Key 1 → Gemini Key 2 → OpenAI Key 1 → OpenAI Key 2

        Parameters
        ----------
        lab_data : LabTestInput
            Validated laboratory test data.

        Returns
        -------
        ClinicalReportOutput
            Structured and validated diagnostic report.

        Raises
        ------
        RuntimeError
            If ALL keys across ALL providers fail.
        """
        formatted_tests = self._format_lab_tests(lab_data.tests)
        patient_label = lab_data.patient_id or "N/A"

        user_message = (
            f"## Patient Laboratory Results\n"
            f"Patient ID: {patient_label}\n\n"
            f"{formatted_tests}"
        )

        prompt = f"{self.SYSTEM_PROMPT}\n\n{user_message}"

        errors = []

        # ── Gemini keys ──────────────────────────────────────────────
        for i, key in enumerate(self.gemini_keys, start=1):
            label = f"Gemini Key {i}"
            try:
                return await self._try_gemini(key, prompt, label)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                logger.warning(
                    "%s failed, trying next… (error: %s)", label, exc
                )

        # ── OpenAI keys ──────────────────────────────────────────────
        for i, key in enumerate(self.openai_keys, start=1):
            label = f"OpenAI Key {i}"
            try:
                return await self._try_openai(key, user_message, label)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                logger.warning(
                    "%s failed, trying next… (error: %s)", label, exc
                )

        # ── All failed ───────────────────────────────────────────────
        error_summary = " | ".join(errors) or "No API keys configured"
        logger.error("All AI providers failed: %s", error_summary)
        raise RuntimeError(f"All AI providers failed. {error_summary}")
