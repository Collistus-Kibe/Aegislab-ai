"""
AegisLab AI — Core AI Inference Engine (Gemini + OpenAI Fallback)
Async service that sends validated lab data to the Gemini API and falls back
to OpenAI GPT-4o if Gemini fails or rate-limits.
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

    **Resilience strategy**: Gemini is the primary model. If it fails for
    any reason (rate-limit, network, bad response), the engine automatically
    falls back to OpenAI GPT-4o using the same prompt and schema.
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
        """Configure both Gemini and OpenAI clients."""
        # ── Primary: Gemini ──────────────────────────────────────────
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Primary model initialized: gemini-2.5-flash")

        # ── Fallback: OpenAI ─────────────────────────────────────────
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("Fallback model initialized: gpt-4o (OpenAI)")

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

    # ── public API ───────────────────────────────────────────────────────

    async def analyze_lab_results(
        self, lab_data: LabTestInput
    ) -> ClinicalReportOutput:
        """
        Send lab results for AI analysis with automatic fallback.

        Flow: Gemini → (on failure) → OpenAI GPT-4o

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
            If both Gemini and OpenAI fail.
        """
        formatted_tests = self._format_lab_tests(lab_data.tests)
        patient_label = lab_data.patient_id or "N/A"

        user_message = (
            f"## Patient Laboratory Results\n"
            f"Patient ID: {patient_label}\n\n"
            f"{formatted_tests}"
        )

        prompt = f"{self.SYSTEM_PROMPT}\n\n{user_message}"

        # ── Attempt 1: Gemini ────────────────────────────────────────
        try:
            logger.info(
                "Sending lab data to Gemini (patient=%s, tests=%d)",
                patient_label,
                len(lab_data.tests),
            )

            response = await self.model.generate_content_async(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                },
            )

            raw_text = response.text
            logger.debug("Raw Gemini response: %s", raw_text[:500])
            return self._parse_and_validate(raw_text, "Gemini")

        except Exception as gemini_exc:
            logger.warning(
                "Gemini failed, falling back to OpenAI... (error: %s)", gemini_exc
            )

        # ── Attempt 2: OpenAI GPT-4o ────────────────────────────────
        try:
            logger.info(
                "Sending lab data to OpenAI GPT-4o (patient=%s, tests=%d)",
                patient_label,
                len(lab_data.tests),
            )

            oai_response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
            )

            raw_text = oai_response.choices[0].message.content
            logger.debug("Raw OpenAI response: %s", raw_text[:500])
            return self._parse_and_validate(raw_text, "OpenAI")

        except Exception as openai_exc:
            logger.error(
                "OpenAI fallback also failed: %s", openai_exc, exc_info=True
            )
            raise RuntimeError(
                f"Both AI providers failed. "
                f"Gemini: {gemini_exc} | OpenAI: {openai_exc}"
            ) from openai_exc
