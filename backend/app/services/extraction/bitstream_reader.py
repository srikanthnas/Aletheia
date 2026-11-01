"""
bitstream_reader.py — Reads LSB-embedded bits from a carrier image.

This is the primary entry point for the extraction pipeline.
It is the exact inverse of lsb_strategy.py's embed() operation.

Protocol (mirrors binary_encoder.py):
    ┌──────────────────────────────┬──────────────────────────────────────────┐
    │  32-bit length header        │  Payload bits                            │
    │  (big-endian, MSB first)     │  (each byte → 8 bits, MSB first)        │
    │  = number of PAYLOAD bytes   │  len(data) × 8 bits                     │
    └──────────────────────────────┴──────────────────────────────────────────┘

Extraction reads exactly:
    32 bits  (header)  +  header_value × 8 bits  (payload)

Design notes:
    - Works for any image embedded with a strategy that uses sequential LSB
      in row-major order (currently LSBStrategy and ADPEStrategy v1).
    - Sprint 4 region-specific extraction can call read_raw_lsbs() directly,
      specifying an offset and bit count per region.
"""

from __future__ import annotations

from PIL import Image


class ExtractionError(Exception):
    """
    Raised when the extraction pipeline cannot recover a valid bitstream.

    Callers should catch this and return an appropriate HTTP 422 response.
    """


# Maximum sane payload size: 1 MB of MIR data.
# Prevents runaway allocation if the image has no valid header.
_MAX_PAYLOAD_BYTES = 1_048_576  # 1 MiB


def read_raw_lsbs(image: Image.Image, n_bits: int, offset: int = 0) -> list[int]:
    """
    Read `n_bits` LSBs from the image starting at channel index `offset`.

    Channels are enumerated in row-major order: R, G, B of pixel (0,0),
    then R, G, B of pixel (1,0), etc.

    Args:
        image:   PIL Image (will be converted to RGB if needed).
        n_bits:  Number of LSBs to read.
        offset:  Channel index to start reading from (default 0).

    Returns:
        list[int] — flat list of 0/1 integers, length == n_bits.

    Raises:
        ExtractionError: If the image has insufficient channels.
    """
    img = image.convert("RGB")
    pixels = list(img.getdata())
    flat: list[int] = []
    for r, g, b in pixels:
        flat.append(r & 1)
        flat.append(g & 1)
        flat.append(b & 1)

    end = offset + n_bits
    if end > len(flat):
        raise ExtractionError(
            f"Requested {n_bits} bits at offset {offset}, but image only has "
            f"{len(flat)} channels total."
        )

    return flat[offset:end]


def read_payload_bitstream(image, offset: int = 0, region_width: int | None = None) -> tuple[int, list[int]]:
    """
    Read the full provenance payload from an LSB-embedded image.

    Steps:
        1. Read the first 32 LSBs → 32-bit big-endian payload byte count.
        2. Validate the declared byte count (sanity check).
        3. Read the next  n_bytes × 8  LSBs → payload bits.

    Args:
        image: PIL Image or np.ndarray that was processed by an LSB-based EmbeddingStrategy.
        offset: Channel index to start reading from (default 0).

    Returns:
        Tuple of (n_payload_bytes, payload_bits):
          - n_payload_bytes: int — number of payload bytes declared in header.
          - payload_bits:  list[int] — payload bits only (header NOT included).

    Raises:
        ExtractionError: If the image is too small, the header is corrupt,
                         or the declared payload exceeds the image capacity.
    """
    import numpy as np
    
    if isinstance(image, np.ndarray):
        img_arr = image
        h, w = img_arr.shape[:2]
    else:
        img = image.convert("RGB")
        img_arr = np.array(img)
        w, h = image.size
        
    total_channels = w * h * 3

    # ------------------------------------------------------------------
    # 1. Read 32-bit header
    # ------------------------------------------------------------------
    if total_channels - offset < 32:
        raise ExtractionError(
            "Image is too small to contain a valid provenance header "
            f"(needs ≥ 32 channels from offset, found {total_channels - offset})."
        )

    # Fast path for non-region specific reads or when reading entire rows
    if not region_width or region_width == w:
        flat_img = img_arr.ravel()
        header_bits = flat_img[offset : offset + 32] & 1
    else:
        # Extract exactly 32 bits from the region
        row_start = offset // (w * 3)
        col_start = (offset % (w * 3)) // 3
        
        region_vals = []
        for r in range(row_start, h):
            if len(region_vals) >= 32:
                break
            c_start = col_start if r == row_start else 0
            c_end = min(c_start + region_width, w)
            region_vals.append(img_arr[r, c_start:c_end, :].ravel())
            
        flat_region = np.concatenate(region_vals) if region_vals else np.array([], dtype=np.uint8)
        if len(flat_region) < 32:
            raise ExtractionError("Out of bounds")
        header_bits = flat_region[:32] & 1

    n_bytes = 0
    for bit in header_bits:
        n_bytes = (n_bytes << 1) | int(bit)

    # ------------------------------------------------------------------
    # 2. Sanity-check declared length
    # ------------------------------------------------------------------
    if n_bytes == 0:
        raise ExtractionError(
            "Header declares 0 payload bytes — this image may not have "
            "provenance data embedded."
        )

    if n_bytes > _MAX_PAYLOAD_BYTES:
        raise ExtractionError(
            f"Header declares {n_bytes:,} bytes, which exceeds the maximum "
            f"allowed payload size ({_MAX_PAYLOAD_BYTES:,} bytes). "
            "The image may not contain Aletheia provenance data."
        )

    # ------------------------------------------------------------------
    # 3. Read payload bits
    # ------------------------------------------------------------------
    payload_bit_count = n_bytes * 8
    total_needed = 32 + payload_bit_count

    if total_channels - offset < total_needed:
        raise ExtractionError(
            f"Header declares {n_bytes} payload bytes ({payload_bit_count} bits), "
            f"but image only has {total_channels - offset - 32} channels after the header."
        )

    payload_bits = []
    
    # Fast path for non-region specific reads or when reading entire rows
    if not region_width or region_width == w:
        flat_img = img_arr.ravel()
        start_idx = offset + 32
        end_idx = offset + total_needed
        if end_idx <= len(flat_img):
            extracted = flat_img[start_idx:end_idx] & 1
            payload_bits = extracted.tolist()
        else:
            raise ExtractionError("Out of bounds when reading payload bits.")
    else:
        # For region extraction, optimize using numpy to slice out exactly what is needed
        row_start = offset // (w * 3)
        col_start = (offset % (w * 3)) // 3
        
        region_vals = []
        for r in range(row_start, h):
            if len(region_vals) >= total_needed:
                break
            
            c_start = col_start if r == row_start else 0
            c_end = min(c_start + region_width, w)
            
            row_data = img_arr[r, c_start:c_end, :].ravel()
            region_vals.append(row_data)
            
        if region_vals:
            flat_region = np.concatenate(region_vals)
            if len(flat_region) >= total_needed:
                extracted = flat_region[32:total_needed] & 1
                payload_bits = extracted.tolist()
            else:
                raise ExtractionError("Out of bounds when reading payload bits.")
        else:
            raise ExtractionError("Out of bounds when reading payload bits.")
        
    return n_bytes, payload_bits
