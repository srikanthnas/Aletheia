"""
binary_encoder.py — Converts a byte payload into a flat binary bitstream.

Format of the produced bitstream:
    ┌──────────────────────────────┬──────────────────────────────────────────┐
    │  32-bit length header        │  Payload bits                            │
    │  (big-endian, MSB first)     │  (each byte → 8 bits, MSB first)        │
    │  = number of PAYLOAD bytes   │  len(data) × 8 bits                     │
    └──────────────────────────────┴──────────────────────────────────────────┘

The 32-bit header allows Sprint 3's extraction module to know exactly how
many payload bytes to read back from a carrier image without needing any
out-of-band information.

Total bitstream length = 32 + len(data) × 8  bits.
"""


def encode(data: bytes) -> list[int]:
    """
    Convert raw bytes into a flat list of bits (integers 0 or 1),
    prepended by a 32-bit big-endian length header.

    Args:
        data: The UTF-8 encoded MIR payload (or any arbitrary bytes).

    Returns:
        list[int] — bitstream ready for consumption by an EmbeddingStrategy.
    """
    n_bytes = len(data)

    # --- 32-bit big-endian length header (MSB first) --------------------
    header_bits: list[int] = []
    for shift in range(31, -1, -1):
        header_bits.append((n_bytes >> shift) & 1)

    # --- Payload bits (each byte, MSB first) ----------------------------
    payload_bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            payload_bits.append((byte >> shift) & 1)

    return header_bits + payload_bits


def decode(bitstream: list[int]) -> bytes:
    """
    Reverse operation: extract the length header, then reconstruct bytes.

    Used by Sprint 3 (Verification Engine) — included here so the
    encoding/decoding contract lives in one place.

    Args:
        bitstream: A flat list of bits (integers 0 or 1) as produced by encode().

    Returns:
        bytes — the original payload.

    Raises:
        ValueError: If the bitstream is shorter than the 32-bit header.
    """
    if len(bitstream) < 32:
        raise ValueError("Bitstream too short to contain a valid length header.")

    # Reconstruct the 32-bit length (number of payload bytes)
    n_bytes = 0
    for bit in bitstream[:32]:
        n_bytes = (n_bytes << 1) | bit

    expected_bits = 32 + n_bytes * 8
    if len(bitstream) < expected_bits:
        raise ValueError(
            f"Bitstream declares {n_bytes} bytes but only "
            f"{(len(bitstream) - 32) // 8} bytes worth of bits are present."
        )

    # Reconstruct each payload byte
    payload = bytearray()
    for i in range(n_bytes):
        byte_bits = bitstream[32 + i * 8 : 32 + (i + 1) * 8]
        byte_val = 0
        for bit in byte_bits:
            byte_val = (byte_val << 1) | bit
        payload.append(byte_val)

    return bytes(payload)
