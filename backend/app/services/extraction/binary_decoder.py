"""
binary_decoder.py — Converts payload bits back into bytes.

Exact inverse of binary_encoder.encode() in the embedding package.

This module is intentionally self-contained: it does not import from
binary_encoder so the extraction package has no dependency on embedding
internals. Both sides share the same bit-packing convention (MSB first),
which is the only coupling needed.

Sprint 4 note:
    If ADPE introduces region-based redundancy (multiple copies of the
    payload), this decoder can be called independently on each region's
    bits and the results compared for integrity checking.
"""

from __future__ import annotations

from app.services.extraction.bitstream_reader import ExtractionError


def bits_to_bytes(payload_bits: list[int]) -> bytes:
    """
    Reconstruct a byte string from a flat list of payload bits (MSB first).

    This operates on PAYLOAD bits only — the 32-bit header must already
    have been consumed by bitstream_reader.read_payload_bitstream().

    Args:
        payload_bits: Flat list of 0/1 integers whose length is a multiple
                      of 8 (i.e. complete bytes).

    Returns:
        bytes — the reconstructed byte payload.

    Raises:
        ExtractionError: If the bit count is not a multiple of 8.
    """
    if len(payload_bits) % 8 != 0:
        raise ExtractionError(
            f"Payload bit count ({len(payload_bits)}) is not a multiple of 8. "
            "The bitstream may be corrupt."
        )

    result = bytearray()
    for i in range(0, len(payload_bits), 8):
        byte_val = 0
        for bit in payload_bits[i : i + 8]:
            byte_val = (byte_val << 1) | bit
        result.append(byte_val)

    return bytes(result)


def decode_full_bitstream(complete_bitstream: list[int]) -> bytes:
    """
    Convenience function: decode a complete bitstream (header + payload).

    Useful when a caller already has the full LSB sequence and wants
    to skip the separate header-reading step.

    Args:
        complete_bitstream: Flat list of bits as returned by
                            read_raw_lsbs() for the full image.

    Returns:
        bytes — the reconstructed payload.

    Raises:
        ExtractionError: If the header is invalid or the bitstream is truncated.
    """
    if len(complete_bitstream) < 32:
        raise ExtractionError("Bitstream too short to contain a valid 32-bit header.")

    # Decode header
    n_bytes = 0
    for bit in complete_bitstream[:32]:
        n_bytes = (n_bytes << 1) | bit

    if n_bytes == 0:
        raise ExtractionError("Header declares 0 payload bytes.")

    total_needed = 32 + n_bytes * 8
    if len(complete_bitstream) < total_needed:
        raise ExtractionError(
            f"Bitstream too short: header declares {n_bytes} bytes "
            f"but only {(len(complete_bitstream) - 32) // 8} bytes available."
        )

    payload_bits = complete_bitstream[32 : 32 + n_bytes * 8]
    return bits_to_bytes(payload_bits)
