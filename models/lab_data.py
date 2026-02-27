"""
AegisLab AI — Pydantic Data Models
Defines validated schemas for laboratory test input and clinical report output.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────────────

class LabTestInput(BaseModel):
    """
    Incoming lab-test payload.

    `tests` accepts dynamic key-value pairs where keys are test names
    (e.g. "Hemoglobin", "MCV", "WBC") and values are the reported results.
    """

    tests: Dict[str, Any] = Field(
        ...,
        description="Key-value map of lab test names to their result values.",
        examples=[{"Hemoglobin": 12.5, "MCV": 78.3, "WBC": 6800}],
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="Optional patient identifier for record linkage.",
    )
    patient_name: Optional[str] = Field(
        default=None,
        description="Optional patient name (used when creating a new patient).",
    )


# ── Response Models ─────────────────────────────────────────────────────────

class ConditionOutput(BaseModel):
    """A single candidate condition with its confidence score."""

    name: str = Field(
        ...,
        description="Name of the suspected clinical condition.",
    )
    confidence_percentage: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence score (0-100 %) for this condition.",
    )


class ClinicalReportOutput(BaseModel):
    """
    Structured diagnostic report returned by the AegisLab AI engine.

    Every field is produced by the LLM and validated against this schema
    before being returned to the caller.
    """

    summary: str = Field(
        ...,
        description="High-level natural-language summary of the lab results.",
    )
    abnormal_values: List[str] = Field(
        ...,
        description="List of lab values flagged as outside normal reference ranges.",
    )
    possible_conditions: List[ConditionOutput] = Field(
        ...,
        description="Ranked list of possible clinical conditions.",
    )
    risk_level: str = Field(
        ...,
        pattern=r"^(LOW|MODERATE|HIGH|CRITICAL)$",
        description="Overall risk classification. Must be LOW, MODERATE, HIGH, or CRITICAL.",
    )
    explanation: str = Field(
        ...,
        description="Detailed clinical reasoning behind the assessment.",
    )
    recommended_actions: List[str] = Field(
        ...,
        description="Suggested next steps (follow-up tests, referrals, etc.).",
    )
    alerts: List[str] = Field(
        ...,
        description="Urgent alerts or critical findings requiring immediate attention.",
    )
