"""
api/routes/embedding.py — POST /api/embed route.

Intentionally thin: validates input, delegates to the provenance embedding
service, and maps the result to the API response schema.

The route has NO knowledge of the embedding algorithm — that lives
exclusively inside the strategy and service layers.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.connection import get_database
from app.services.provenance_embedding_service import embed_provenance
from app.schemas.embedding import EmbedRequest, EmbedResponse

router = APIRouter()


@router.post(
    "/embed",
    response_model=EmbedResponse,
    summary="Embed provenance into a registered media asset",
    description=(
        "Retrieves a registered image by its UUID, constructs a Media Identity Record (MIR), "
        "serialises it, and embeds it into the image using the active embedding strategy (LSB). "
        "Returns a download URL for the provenance-embedded PNG."
    ),
)
async def embed_media_endpoint(
    request: EmbedRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Accepts JSON body: { "image_id": "<uuid>" }

    Returns:
        status         — "success"
        embedded_image — relative URL to the embedded PNG (served via /uploads)
        embedded_bits  — total bits embedded (32-bit header + MIR payload)
    """
    result = await embed_provenance(image_id=request.image_id, db=db)

    return EmbedResponse(
        status="success",
        embedded_image=result.download_url,
        embedded_bits=result.embedded_bits,
    )
