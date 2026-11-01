"""
api/routes/assessment.py — POST /api/assess: full end-to-end Aletheia pipeline.

This route is the primary entry point for the complete three-layer pipeline:

  Layer 2 (AI Forensics)  ──────────────────────────────────────────────┐
                                                                          ├──► TrustEngine ──► TrustResponse
  Layer 1 (Provenance Extraction → Verification) ──────────────────────┘

Design
------
- AI Forensics always runs, regardless of whether provenance is present.
- Provenance extraction and verification are attempted but failures are
  gracefully handled (images without watermarks are valid inputs).
- Three provenance states are handled:
    1. No watermark found     → verification_result=None, mir_recovered=False
    2. MIR found, unregistered → verification_result=None, mir_recovered=True
    3. Full verification       → verification_result=VerificationResult
- All ML inference is run off the async event loop via run_in_threadpool.

This route is intentionally more detailed than the sprint-specific routes
because it orchestrates three independent layers. All business logic remains
in the respective service layers.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image

from app.database.connection import get_database
from app.services.ai_forensics.detection_engine import DetectionEngine
from app.services.verification.verification_service import (
    VerificationResult,
    verify_provenance,
)
from app.services.trust.trust_engine import TrustEngine
from app.schemas.trust import (
    TrustResponse,
    ProvenanceEvidenceSchema,
    ForensicsEvidenceSchema,
    DetectorBreakdownItem,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Singletons — initialized once at module load time.
# The CLIP model is lazy-loaded on first inference call.
# ---------------------------------------------------------------------------
_forensics_engine = DetectionEngine.default()
_trust_engine = TrustEngine()


@router.post(
    "/assess",
    response_model=TrustResponse,
    summary="Full End-to-End Aletheia Assessment",
    description=(
        "Runs the complete Aletheia three-layer pipeline on an uploaded image:\n\n"
        "**Layer 2** — AI Forensics Engine (CLIP + Statistical + Artifact + Frequency detectors)\n\n"
        "**Layer 1** — Provenance Extraction + Verification (requires prior Aletheia embedding)\n\n"
        "**Layer 3** — Trust & Decision Engine (rule-based evidence fusion)\n\n"
        "Returns a unified `TrustResponse` with verdict, trust score, confidence, "
        "and full evidence breakdown. Does NOT require prior registration — "
        "provenance extraction is attempted blind and gracefully fails if no "
        "Aletheia watermark is present."
    ),
)
async def assess_image(
    file: UploadFile = File(
        ...,
        description=(
            "Image to analyze. PNG is recommended for registered images "
            "(lossless format preserves embedded provenance). "
            "Any format accepted for forensics-only analysis."
        ),
    ),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrustResponse:
    """
    POST /api/assess — Full three-layer Aletheia analysis.

    Returns a unified TrustAssessment combining all evidence streams.
    """
    # ----------------------------------------------------------------
    # Read and decode the uploaded image
    # ----------------------------------------------------------------
    contents = await file.read()

    try:
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot open uploaded file as an image: {exc}",
        )

    # ----------------------------------------------------------------
    # Layer 2 — AI Forensics Engine
    # Runs first, independently of provenance status.
    # Run off the async event loop to avoid blocking.
    # ----------------------------------------------------------------
    try:
        ai_result = await run_in_threadpool(_forensics_engine.run, image)
    except Exception as exc:
        logger.error(
            "[AssessRoute] AI Forensics engine error: %s", exc, exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"AI Forensics engine error: {exc}",
        )

    # ----------------------------------------------------------------
    # Layer 1 — Provenance Verification
    # Attempt full verification. Gracefully handle all failure modes:
    #   422 "MIR extraction failed" → no watermark (mir_recovered=False)
    #   404                          → MIR found, image not in registry (mir_recovered=True)
    #   422 "No pHash stored"        → registered but never embedded (mir_recovered=True)
    #   success                      → full VerificationResult
    # ----------------------------------------------------------------
    verification_result: Optional[VerificationResult] = None
    mir_recovered: bool = False

    try:
        verification_result = await verify_provenance(image=image, db=db)
        mir_recovered = True
        logger.debug(
            "[AssessRoute] Full verification succeeded: media_id=%s, verdict=%s",
            verification_result.media_id,
            verification_result.verification,
        )

    except HTTPException as exc:
        detail_str: str = str(exc.detail) if exc.detail else ""

        if exc.status_code == 422 and (
            "MIR extraction failed" in detail_str
            or "no valid provenance" in detail_str.lower()
        ):
            # No Aletheia watermark in this image — entirely normal
            logger.info("[AssessRoute] No provenance watermark found in image.")
            mir_recovered = False

        elif exc.status_code == 404:
            # MIR was recovered but the image is not in the registry
            logger.info(
                "[AssessRoute] MIR recovered but image not registered in DB: %s",
                detail_str,
            )
            mir_recovered = True

        elif exc.status_code == 422:
            # Image registered but pHash missing (embed was not performed, or pHash lost)
            logger.warning(
                "[AssessRoute] Verification incomplete (registered but missing pHash): %s",
                detail_str,
            )
            mir_recovered = True

        else:
            logger.warning(
                "[AssessRoute] Unexpected verification HTTP error %d: %s",
                exc.status_code,
                detail_str,
            )

    except Exception as exc:
        # Non-HTTP exception during verification — log and continue gracefully
        logger.warning(
            "[AssessRoute] Unexpected verification error: %s", exc, exc_info=True
        )

    # ----------------------------------------------------------------
    # Layer 3 — Trust & Decision Engine
    # Fuse evidence from both layers into a single TrustAssessment.
    # ----------------------------------------------------------------
    assessment = _trust_engine.assess(
        ai_evidence=ai_result,
        verification_result=verification_result,
        mir_recovered=mir_recovered,
    )

    # ----------------------------------------------------------------
    # Build API response from the assessment
    # ----------------------------------------------------------------
    prov_schema: Optional[ProvenanceEvidenceSchema] = None
    if assessment.provenance_evidence is not None:
        pe = assessment.provenance_evidence
        prov_schema = ProvenanceEvidenceSchema(
            available=pe.available,
            mir_recovered=pe.mir_recovered,
            provenance_verdict=pe.provenance_verdict,
            integrity_score=pe.integrity_score,
            similarity=pe.similarity,
            hamming_distance=pe.hamming_distance,
            recovered_regions=pe.recovered_regions,
            total_regions=pe.total_regions,
            inconsistent=pe.inconsistent,
            pixel_hash_match=pe.pixel_hash_match,
            media_id=pe.media_id,
            dhash_similarity=pe.dhash_similarity,
            local_similarity=pe.local_similarity,
            changed_area_percentage=pe.changed_area_percentage,
            tamper_type=pe.tamper_type,
            severity=pe.severity,
        )

    fore_schema: Optional[ForensicsEvidenceSchema] = None
    if assessment.forensics_evidence is not None:
        fe = assessment.forensics_evidence
        fore_schema = ForensicsEvidenceSchema(
            ai_probability=fe.ai_probability,
            confidence=fe.confidence,
            forensics_verdict=fe.forensics_verdict,
            detector_count=fe.detector_count,
            explanation=fe.explanation,
            detector_scores=fe.detector_scores,
        )

    detector_breakdown = [
        DetectorBreakdownItem(
            engine=r.engine,
            score=r.score,
            confidence=r.confidence,
            reason=r.reason,
            metadata=r.metadata,
        )
        for r in ai_result.detector_breakdown
    ]

    return TrustResponse(
        trust_score=assessment.trust_score,
        verdict=assessment.verdict,
        confidence=assessment.confidence,
        reasoning=assessment.reasoning,
        provenance_available=assessment.provenance_available,
        provenance_verdict=assessment.provenance_verdict,
        forensics_verdict=assessment.forensics_verdict,
        ai_probability=assessment.ai_probability,
        integrity_score=assessment.integrity_score,
        evidence_summary=assessment.evidence_summary,
        provenance_evidence=prov_schema,
        forensics_evidence=fore_schema,
        detector_breakdown=detector_breakdown,
    )
