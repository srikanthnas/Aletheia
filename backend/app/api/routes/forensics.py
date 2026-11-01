"""
api/routes/forensics.py — AI Forensics Engine API endpoints.

Exposes Engine 2 (AI Forensics) as a standalone REST endpoint.
Does NOT modify or interact with Engine 1 (Provenance Recovery).
"""
from __future__ import annotations

import io
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image

from app.services.ai_forensics.detection_engine import DetectionEngine

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Engine singleton — initialized once at module load time.
# The CLIP model is lazy-loaded on first inference call.
# ---------------------------------------------------------------------------
_engine = DetectionEngine.default()


@router.post(
    "/analyze",
    summary="AI Forensics Analysis",
    description=(
        "Runs the AI Forensics Engine (Layer 2) on an uploaded image. "
        "Returns an ensemble AI evidence score from multiple independent detectors. "
        "Does NOT require a registered MIR — operates blindly on raw image content."
    ),
)
async def analyze_image(
    file: UploadFile = File(..., description="Image to forensically analyze."),
):
    """
    POST /api/forensics/analyze

    Runs the full AI Forensics Engine — CLIP foundation detector + statistical
    detector — and returns a fused AIEvidenceResult.
    """
    contents = await file.read()

    try:
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot open uploaded file as an image: {exc}",
        )

    # Run ML inference off the async event loop to avoid blocking
    try:
        result = await run_in_threadpool(_engine.run, image)
    except Exception as exc:
        logger.error("[ForensicsRoute] Engine error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Forensics engine error: {exc}",
        )

    return {
        "ai_probability":   result.ai_probability,
        "confidence":       result.confidence,
        "verdict":          result.verdict,
        "explanation":      result.explanation,
        "detector_breakdown": [
            {
                "engine":     r.engine,
                "score":      r.score,
                "confidence": r.confidence,
                "reason":     r.reason,
                "metadata":   r.metadata,
            }
            for r in result.detector_breakdown
        ],
    }


@router.get(
    "/status",
    summary="AI Forensics Engine Status",
    description="Returns the list of active detector plugins registered in the engine.",
)
async def engine_status():
    """GET /api/forensics/status — health and plugin registry check."""
    return {
        "status": "active",
        "registered_detectors": [d.name for d in _engine.detectors()],
        "engine": "AI Forensics Engine (Layer 2)",
    }
