"""
provenance_embedding_service.py — Orchestrates the full provenance embedding pipeline.

Responsibilities:
  1. Fetch the registered media document from MongoDB by image_id.
  2. Construct the Media Identity Record (MIR).
  3. Serialise the MIR to UTF-8 JSON bytes.
  4. Encode bytes into a binary bitstream (with 32-bit length header).
  5. Load the original image from disk.
  6. Delegate embedding to an injected EmbeddingStrategy (LSB by default).
  7. Save the embedded image as PNG alongside the original.
  8. Update the MongoDB document with the embedded image path.
  9. Return a structured result.

Design note — Dependency Injection:
  The `strategy` parameter accepts any EmbeddingStrategy implementation.
  Sprint 3 can pass an ADPEStrategy instance here without modifying this file.
"""

import os
from dataclasses import dataclass

from fastapi import HTTPException
from PIL import Image

from app.services.embedding import (
    EmbeddingStrategy,
    build_mir,
    serialize,
    encode,
)
from app.services.dct.dct_strategy import DCTStrategy
from app.services.dct.robust_codec import encode_robust
from app.core.config import settings


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EmbedResult:
    """Structured return value from embed_provenance()."""

    embedded_image_path: str
    """Absolute path to the saved embedded image on disk."""

    download_url: str
    """Relative URL path (served via /uploads static mount)."""

    embedded_bits: int
    """Total number of bits written into the carrier image (header + payload)."""

    success: bool = True


# ---------------------------------------------------------------------------
# Service function
# ---------------------------------------------------------------------------

async def embed_provenance(
    image_id: str,
    db,
    strategy: EmbeddingStrategy | None = None,
) -> EmbedResult:
    """
    Execute the full provenance embedding pipeline.

    Args:
        image_id: UUID of the registered media asset (from Sprint 1).
        db:       Motor AsyncIOMotorDatabase instance (injected via FastAPI dependency).
        strategy: EmbeddingStrategy implementation to use.
                  Defaults to LSBStrategy (sequential LSB, Sprint 2).
                  Pass a different strategy to swap algorithms without changing
                  this function or the API route.

    Returns:
        EmbedResult with embedded image path, download URL, bit count, and success flag.

    Raises:
        HTTPException 404: If image_id is not found in the registry.
        HTTPException 422: If the image is too small to hold the MIR payload.
        HTTPException 500: For unexpected I/O or processing errors.
    """

    # Use DCTStrategy as the production default (DCT-QIM, Sprint 6 integration)
    if strategy is None:
        strategy = DCTStrategy(distributed=True)

    # ------------------------------------------------------------------
    # 1. Fetch registered media document
    # ------------------------------------------------------------------
    collection = db["registered_media"]
    doc = await collection.find_one({"image_id": image_id})

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"No registered media found with image_id='{image_id}'.",
        )

    # ------------------------------------------------------------------
    # 2. Build MIR from stored provenance fields
    # ------------------------------------------------------------------
    mir = build_mir(
        media_id=doc["image_id"],
        model_name=doc["model_name"],
        timestamp=doc["timestamp"],
        media_type=doc.get("media_type", "image"),
    )

    # ------------------------------------------------------------------
    # 3. Serialise MIR → UTF-8 JSON bytes
    # ------------------------------------------------------------------
    mir_bytes = serialize(mir)

    # ------------------------------------------------------------------
    # 4. Encode bytes → binary bitstream (with 32-bit length header)
    # ------------------------------------------------------------------
    # Production provenance uses an error-correcting, interleaved frame.
    # The legacy raw encoder remains available to compatibility/experimental routes.
    bitstream = encode_robust(mir_bytes)

    # ------------------------------------------------------------------
    # 5. Load original image
    # ------------------------------------------------------------------
    original_path: str = doc["upload_path"]

    if not os.path.exists(original_path):
        raise HTTPException(
            status_code=500,
            detail=f"Original image file not found on disk: '{original_path}'.",
        )

    try:
        original_image = Image.open(original_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open original image: {exc}",
        )

    # ------------------------------------------------------------------
    # 6. Embed via injected strategy
    # ------------------------------------------------------------------
    try:
        embedded_image = strategy.embed(original_image, bitstream)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # ------------------------------------------------------------------
    # 7. Save embedded image as PNG (lossless — required for LSB integrity)
    # ------------------------------------------------------------------
    embedded_filename = f"{image_id}_embedded.png"
    embedded_path = os.path.join(settings.UPLOAD_DIR, embedded_filename)

    try:
        embedded_image.save(embedded_path, format="PNG", optimize=False)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save embedded image: {exc}",
        )

    # ------------------------------------------------------------------
    # 8. Generate pHash of the embedded image (Sprint 4)
    #    Wrapped in try/except — pHash failure must never block embedding.
    # ------------------------------------------------------------------
    phash_hex: str | None = None
    pixel_hash_hex: str | None = None
    dhash_hex: str | None = None
    try:
        from app.services.verification.phash_service import generate_phash
        phash_hex = generate_phash(embedded_image)
    except Exception:
        pass  # Non-fatal; verification will surface a clear error if missing

    try:
        from app.services.verification.pixel_hash_service import generate_pixel_hash
        pixel_hash_hex = generate_pixel_hash(embedded_image)
    except Exception:
        pass

    try:
        from app.services.integrity.integrity_features import dhash_hex as generate_dhash
        dhash_hex = generate_dhash(embedded_image)
    except Exception:
        pass

    strategy_name: str = (
        getattr(strategy, "ROBUST_STRATEGY_NAME", None)
        if getattr(strategy, "distributed", False)
        else getattr(strategy, "STRATEGY_NAME", "sequential_lsb")
    )

    # ------------------------------------------------------------------
    # 9. Update MongoDB document
    # ------------------------------------------------------------------
    update_fields: dict = {
        "embedded_image_path": embedded_path,
        "embedded_bits":       len(bitstream),
        "mir":                 mir.to_dict(),
        "embedding_strategy":  strategy_name,
    }
    if phash_hex:
        update_fields["phash"] = phash_hex
    if pixel_hash_hex:
        update_fields["pixel_hash"] = pixel_hash_hex
    if dhash_hex:
        update_fields["dhash"] = dhash_hex

    await collection.update_one(
        {"image_id": image_id},
        {"$set": update_fields},
    )

    # ------------------------------------------------------------------
    # 9. Return structured result
    # ------------------------------------------------------------------
    download_url = f"/uploads/{embedded_filename}"

    return EmbedResult(
        embedded_image_path=embedded_path,
        download_url=download_url,
        embedded_bits=len(bitstream),
        success=True,
    )
