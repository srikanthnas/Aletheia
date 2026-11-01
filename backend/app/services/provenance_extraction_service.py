"""
provenance_extraction_service.py — Orchestrates the full provenance extraction pipeline.

Responsibilities:
  1. Accept a PIL Image (already opened by the route handler).
  2. Read the LSB bitstream (header + payload bits).
  3. Decode payload bits back into bytes.
  4. Deserialise bytes into a MediaIdentityRecord.
  5. Determine which embedding strategy was used (from DB or heuristic).
  6. Return a structured ExtractionResult.

Design:
    The extraction pipeline is intentionally strategy-agnostic at this layer.
    Sprint 4 can add:
      - A strategy-detection step (e.g. check for ADPE watermark in first region).
      - Region-specific extraction for distributed payloads.
      - pHash / Hamming integrity comparison.
    None of those changes will require modifying the route or schemas.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image
from fastapi import HTTPException

from app.services.extraction import (
    ExtractionError,
    read_payload_bitstream,
    bits_to_bytes,
    deserialize,
)
from app.services.embedding.mir_serializer import MediaIdentityRecord
from app.services.extraction.region_manager import RegionManager



# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Structured return value from extract_provenance()."""

    mir: MediaIdentityRecord
    """The recovered Media Identity Record."""

    strategy_used: str
    """Name of the embedding strategy detected (or inferred)."""

    n_payload_bytes: int
    """Number of payload bytes recovered from the image."""

    recovered_regions: int
    """Number of regions where a valid MIR was recovered."""

    total_regions: int
    """Total number of regions in the adaptive grid."""

    inconsistent: bool
    """True if different MIRs were recovered across regions."""

    success: bool = True


# ---------------------------------------------------------------------------
# Strategy detection heuristic
# ---------------------------------------------------------------------------

def _detect_strategy(image: Image.Image, db_strategy: str | None) -> str:
    """
    Determine the embedding strategy used.

    Priority:
      1. If the MongoDB document has a stored strategy name, use it.
      2. Otherwise fall back to "sequential_lsb" (the Sprint 2 default).

    Sprint 4 can extend this to inspect image metadata or perform a
    region-scan to distinguish LSB from ADPE.

    Args:
        image:       The carrier image (may be used for heuristics later).
        db_strategy: Strategy name stored in MongoDB, or None.

    Returns:
        str — strategy identifier for the API response.
    """
    if db_strategy:
        return db_strategy
    return "sequential_lsb"


# ---------------------------------------------------------------------------
# Service function
# ---------------------------------------------------------------------------

async def extract_provenance(
    image: Image.Image,
    db=None,
) -> ExtractionResult:
    """
    Execute the full provenance extraction pipeline.

    Args:
        image: A PIL Image object (the embedded carrier).
        db:    Optional Motor database (used to look up stored strategy metadata).
               If None, strategy is inferred from heuristics.

    Returns:
        ExtractionResult with the recovered MIR, strategy name, and byte count.

    Raises:
        HTTPException 422: If no valid provenance data is found in the image.
        HTTPException 500: For unexpected processing errors.
    """

    # ------------------------------------------------------------------
    # 1. PRIMARY PATH — distributed, error-correcting DCT-QIM/RDM
    # ------------------------------------------------------------------
    from app.services.dct.qim_extractor import extract_bitstream as dct_extract
    from app.services.dct.distributed_layout import regions_for
    from app.services.dct.coefficient_selector import get_embeddable_coefficients
    from app.services.dct.robust_codec import decode_robust, decode_header, frame_bit_length, HEADER_SIZE

    valid_mirs: list[MediaIdentityRecord] = []
    recovered_bytes = 0
    distributed_regions = regions_for(image)
    total_regions = len(distributed_regions)

    # Every production region carries the same robust MIR.  Recover each region
    # independently so localized edits/copy-paste operations do not destroy the
    # only provenance copy.
    for region in distributed_regions:
        crop = image.crop((region.x, region.y, region.x + region.width, region.y + region.height))
        capacity = (crop.width // 8) * (crop.height // 8) * len(get_embeddable_coefficients())
        try:
            # Header is fixed-size Hamming coded: 10 bytes * 14 bits.
            header_len = HEADER_SIZE * 14
            header_bits = dct_extract(crop, q_step=16.0, max_bits=header_len)
            # We need the header to learn the payload length. Decode the fixed
            # header via decode_robust only after reading enough of the frame.
            if len(header_bits) < header_len:
                continue
            version, payload_len, _, _ = decode_header(header_bits)
            needed = frame_bit_length(payload_len)
            if needed > capacity:
                continue
            probe = dct_extract(crop, q_step=16.0, max_bits=needed)
            payload_bytes, meta = decode_robust(probe)
            mir = deserialize(payload_bytes)
            valid_mirs.append(mir)
            recovered_bytes = max(recovered_bytes, len(payload_bytes))
        except Exception:
            continue

    # ------------------------------------------------------------------
    # 1b. LEGACY DCT-QIM compatibility path
    # ------------------------------------------------------------------
    if not valid_mirs:
        total_regions = 1
        try:
            raw_bits = dct_extract(image, q_step=16.0, max_bits=32)
            if len(raw_bits) >= 32:
                n_bytes = 0
                for bit in raw_bits[:32]:
                    n_bytes = (n_bytes << 1) | bit
                if 0 < n_bytes <= 1_048_576:
                    total_bits_needed = 32 + n_bytes * 8
                    full_bits = dct_extract(image, q_step=16.0, max_bits=total_bits_needed)
                    if len(full_bits) >= total_bits_needed:
                        mir = deserialize(bits_to_bytes(full_bits[32:total_bits_needed]))
                        valid_mirs.append(mir)
                        recovered_bytes = n_bytes
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 2. COMPATIBILITY FALLBACK — LSB / ADPE Multi-Region Extraction
    #    Activated only when DCT extraction finds no valid MIR.
    #    Handles images embedded with the old ADPEStrategy / LSBStrategy.
    # ------------------------------------------------------------------
    if not valid_mirs:
        region_manager = RegionManager()
        regions = region_manager.partition(image)
        w, h = image.size
        total_regions = len(regions)

        import numpy as np
        img_arr_cached = np.array(image.convert("RGB"))
        
        for region in regions:
            offset = (region.y * w + region.x) * 3
            try:
                n_payload_bytes, payload_bits = read_payload_bitstream(
                    img_arr_cached, offset=offset, region_width=region.width
                )
                payload_bytes = bits_to_bytes(payload_bits)
                mir = deserialize(payload_bytes)
                valid_mirs.append(mir)
                recovered_bytes = n_payload_bytes
            except Exception:
                continue

    if not valid_mirs:
        raise HTTPException(
            status_code=422,
            detail="MIR extraction failed — no valid provenance data found. "
                   "The image may not contain Aletheia provenance, or it may have been "
                   "processed by an unsupported tool."
        )

    # ------------------------------------------------------------------
    # 2. Check for Consistency
    # ------------------------------------------------------------------
    first_mir_dict = valid_mirs[0].to_dict()
    inconsistent = any(mir.to_dict() != first_mir_dict for mir in valid_mirs)
    
    # We proceed with the most prominent (first) MIR
    final_mir = valid_mirs[0]

    # ------------------------------------------------------------------
    # 4. Determine embedding strategy
    #    Optionally look up the media_id in MongoDB for richer metadata.
    # ------------------------------------------------------------------
    db_strategy = None
    if db is not None:
        try:
            doc = await db["registered_media"].find_one({"image_id": final_mir.media_id})
            if doc:
                db_strategy = doc.get("embedding_strategy")
        except Exception:
            pass  # Non-fatal: strategy lookup failure does not block extraction

    strategy_used = _detect_strategy(image, db_strategy)

    # ------------------------------------------------------------------
    # 5. Return structured result
    # ------------------------------------------------------------------
    return ExtractionResult(
        mir=final_mir,
        strategy_used=strategy_used,
        n_payload_bytes=recovered_bytes,
        recovered_regions=len(valid_mirs),
        total_regions=total_regions,
        inconsistent=inconsistent,
        success=True,
    )
