"""
api/routes/extraction.py — POST /api/extract route.

Accepts an embedded image file upload, delegates to the provenance
extraction service, and returns the recovered MIR.

This route is intentionally thin — all pipeline logic lives in
provenance_extraction_service.py.
"""

import io

from fastapi import APIRouter, Depends, File, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image

from app.database.connection import get_database
from app.services.provenance_extraction_service import extract_provenance
from app.schemas.extraction import ExtractionResponse, RecoveredMIR

router = APIRouter()


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Extract provenance from an embedded image",
    description=(
        "Uploads an LSB-embedded image and recovers the Media Identity Record (MIR) "
        "that was written into it by the Provenance Embedding Engine (Sprint 2). "
        "Returns the recovered MIR and the embedding strategy detected."
    ),
)
async def extract_provenance_endpoint(
    file: UploadFile = File(
        ...,
        description=(
            "PNG image produced by POST /api/embed. "
            "Must be a lossless format (PNG) — JPEG will corrupt the embedded bits."
        ),
    ),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Pipeline:
        1. Read uploaded file bytes.
        2. Open as PIL Image.
        3. Delegate to extract_provenance().
        4. Map ExtractionResult → ExtractionResponse.
    """
    # Read file bytes
    contents = await file.read()

    # Open as PIL Image
    try:
        image = Image.open(io.BytesIO(contents))
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Could not open the uploaded file as an image: {exc}",
        )

    # Delegate to service
    result = await extract_provenance(image=image, db=db)

    # Map to response schema
    return ExtractionResponse(
        status="success",
        strategy_used=result.strategy_used,
        mir=RecoveredMIR(**result.mir.to_dict()),
    )
