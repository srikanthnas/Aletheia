"""
api/routes/verification.py — POST /api/verify route.

Accepts an uploaded image file, delegates to verify_provenance(), and maps
the result to VerifyResponse. No business logic lives here.
"""

import io

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image

from app.database.connection import get_database
from app.services.verification.verification_service import verify_provenance
from app.schemas.verification import VerifyResponse

router = APIRouter()


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify provenance of an embedded image",
    description=(
        "Uploads an Aletheia-embedded image. The engine extracts the MIR, "
        "generates a perceptual hash (pHash), retrieves the stored pHash from "
        "the registry, computes Hamming Distance, and returns a full verification report."
    ),
)
async def verify_media_endpoint(
    file: UploadFile = File(
        ...,
        description="PNG image produced by POST /api/embed (lossless format required).",
    ),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    contents = await file.read()

    try:
        image = Image.open(io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot open uploaded file as an image: {exc}",
        )

    result = await verify_provenance(image=image, db=db)

    return VerifyResponse(
        status=result.status,
        media_id=result.media_id,
        model_name=result.model_name,
        timestamp=result.timestamp,
        media_type=result.media_type,
        framework=result.framework,
        strategy=result.strategy,
        uploaded_phash=result.uploaded_phash,
        stored_phash=result.stored_phash,
        hamming_distance=result.hamming_distance,
        similarity=result.similarity,
        recovered_regions=result.recovered_regions,
        total_regions=result.total_regions,
        recovery_percentage=result.recovery_percentage,
        integrity_score=result.integrity_score,
        observation=result.observation,
        verification=result.verification,
        pixel_hash_match=result.pixel_hash_match,
        uploaded_dhash=result.uploaded_dhash,
        stored_dhash=result.stored_dhash,
        dhash_similarity=result.dhash_similarity,
        local_similarity=result.local_similarity,
        changed_area_percentage=result.changed_area_percentage,
        histogram_distance=result.histogram_distance,
        edge_density_delta=result.edge_density_delta,
        high_frequency_ratio=result.high_frequency_ratio,
    )
