"""
AegisLab AI — Diagnostics API Routes
Secured endpoints for submitting lab data for AI analysis.
Results are persisted to TiDB and protected by Firebase auth.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import LabRecord, Patient, get_db
from core.security import verify_user
from models.lab_data import ClinicalReportOutput, LabTestInput
from services.aegis_engine import AegisAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])

analyzer = AegisAnalyzer()


@router.post(
    "/analyze",
    response_model=ClinicalReportOutput,
    summary="Analyze lab results",
    description="Submit lab test data for AI-powered clinical analysis. "
    "Requires a valid Firebase Bearer token.",
)
async def analyze_lab_results(
    data: LabTestInput,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(verify_user),
) -> ClinicalReportOutput:
    """
    1. Validate incoming lab data via Pydantic.
    2. Run AI inference through AegisAnalyzer (Gemini).
    3. Persist the record to TiDB.
    4. Return the structured clinical report.
    """
    try:
        # ── AI Inference ─────────────────────────────────────────────
        result = await analyzer.analyze_lab_results(data)

        # ── Auto-create Patient if needed ─────────────────────────────
        if data.patient_id:
            existing = await db.execute(
                select(Patient).where(
                    Patient.patient_ref == data.patient_id,
                    Patient.user_id == user_id,
                )
            )
            if not existing.scalars().first():
                new_patient = Patient(
                    user_id=user_id,
                    patient_ref=data.patient_id,
                    name=data.patient_name or "Unknown Patient",
                )
                db.add(new_patient)
                await db.commit()
                logger.info("Auto-created patient %s for user %s", data.patient_id, user_id)

        # ── Persist to TiDB ──────────────────────────────────────────
        new_record = LabRecord(
            user_id=user_id,
            patient_id=data.patient_id,
            raw_data=data.tests,
            ai_summary=result.summary,
            risk_level=result.risk_level,
        )
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)

        logger.info(
            "Lab record %d saved for user %s (risk=%s)",
            new_record.id,
            user_id,
            result.risk_level,
        )

        return result

    except (ValueError, RuntimeError) as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI analysis failed: {exc}",
        )

    except Exception as exc:
        logger.error("Unexpected error in /analyze: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again.",
        )


@router.get(
    "/history/{patient_id}",
    summary="Get patient history",
    description="Retrieve all past lab analysis records for a given patient. "
    "Requires a valid Firebase Bearer token.",
)
async def get_patient_history(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(verify_user),
):
    """
    Fetch all lab records for a specific patient, ordered by most recent first.
    Only accessible to authenticated users.
    """
    try:
        query = (
            select(LabRecord)
            .where(LabRecord.patient_id == patient_id)
            .order_by(LabRecord.created_at.desc())
        )
        result = await db.execute(query)
        records = result.scalars().all()

        logger.info(
            "Returning %d history records for patient %s (user=%s)",
            len(records),
            patient_id,
            user_id,
        )

        return [
            {
                "id": r.id,
                "patient_id": r.patient_id,
                "raw_data": r.raw_data,
                "ai_summary": r.ai_summary,
                "risk_level": r.risk_level,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    except Exception as exc:
        logger.error("Failed to fetch history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient history.",
        )


@router.get(
    "/patients",
    summary="List patients",
    description="Return all patients belonging to the authenticated user.",
)
async def list_patients(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(verify_user),
):
    """Fetch all patient profiles for the current user."""
    try:
        query = (
            select(Patient)
            .where(Patient.user_id == user_id)
            .order_by(Patient.created_at.desc())
        )
        result = await db.execute(query)
        patients = result.scalars().all()

        return [
            {
                "id": p.id,
                "patient_ref": p.patient_ref,
                "name": p.name,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in patients
        ]

    except Exception as exc:
        logger.error("Failed to list patients: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patients.",
        )
