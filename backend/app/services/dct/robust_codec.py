"""Error-correcting wire format for persistent Aletheia provenance.

The legacy wire format is a raw 32-bit length + payload.  That format is very
fragile: one corrupted bit can make the JSON undecodable.  This module adds a
small, dependency-free Hamming(7,4) code, interleaving, CRC32, and a fixed
magic/version/length header so the embedded MIR can tolerate scattered bit
errors while remaining compact enough for regional DCT embedding.
"""
from __future__ import annotations

import struct
import zlib

MAGIC = b"AL"
VERSION = 1
HEADER_FMT = ">2sBHI"  # magic, version, payload length, crc32
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAX_PAYLOAD = 65535


def _hamming_encode_nibble(n: int) -> list[int]:
    d1 = (n >> 0) & 1
    d2 = (n >> 1) & 1
    d3 = (n >> 2) & 1
    d4 = (n >> 3) & 1
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p4 = d2 ^ d3 ^ d4
    return [p1, p2, d1, p4, d2, d3, d4]


def _hamming_decode_codeword(code: list[int]) -> tuple[int, bool]:
    b = [0] + [int(x) & 1 for x in code[:7]]
    if len(code) < 7:
        return 0, False
    s1 = b[1] ^ b[3] ^ b[5] ^ b[7]
    s2 = b[2] ^ b[3] ^ b[6] ^ b[7]
    s4 = b[4] ^ b[5] ^ b[6] ^ b[7]
    syndrome = s1 | (s2 << 1) | (s4 << 2)
    if syndrome:
        if syndrome > 7:
            return 0, False
        b[syndrome] ^= 1
    nibble = b[3] | (b[5] << 1) | (b[6] << 2) | (b[7] << 3)
    return nibble, True


def _bytes_to_bits(data: bytes) -> list[int]:
    out: list[int] = []
    for byte in data:
        out.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
    return out


def _bits_to_bytes(bits: list[int]) -> bytes:
    usable = len(bits) - (len(bits) % 8)
    out = bytearray()
    for i in range(0, usable, 8):
        v = 0
        for bit in bits[i:i + 8]:
            v = (v << 1) | (int(bit) & 1)
        out.append(v)
    return bytes(out)


def _hamming_encode(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        bits.extend(_hamming_encode_nibble(byte & 0x0F))
        bits.extend(_hamming_encode_nibble(byte >> 4))
    return bits


def _hamming_decode(bits: list[int]) -> tuple[bytes, int, int]:
    out = bytearray()
    corrected = 0
    failed = 0
    usable = len(bits) - (len(bits) % 14)
    for i in range(0, usable, 14):
        lo, ok1 = _hamming_decode_codeword(bits[i:i + 7])
        hi, ok2 = _hamming_decode_codeword(bits[i + 7:i + 14])
        if not ok1 or not ok2:
            failed += 1
            continue
        # A Hamming codeword is corrected when its syndrome was non-zero.
        for codeword in (bits[i:i + 7], bits[i + 7:i + 14]):
            if len(codeword) == 7:
                b = [0] + [int(x) & 1 for x in codeword]
                syndrome = (b[1] ^ b[3] ^ b[5] ^ b[7]) | ((b[2] ^ b[3] ^ b[6] ^ b[7]) << 1) | ((b[4] ^ b[5] ^ b[6] ^ b[7]) << 2)
                corrected += int(syndrome != 0)
        out.append((hi << 4) | lo)
    return bytes(out), corrected, failed


def _interleave(bits: list[int], columns: int = 17) -> list[int]:
    """Matrix interleave spreads burst errors across Hamming codewords."""
    if not bits:
        return []
    rows = (len(bits) + columns - 1) // columns
    padded = bits + [0] * (rows * columns - len(bits))
    return [padded[r * columns + c] for c in range(columns) for r in range(rows)]


def _deinterleave(bits: list[int], original_len: int, columns: int = 17) -> list[int]:
    if not bits or original_len <= 0:
        return []
    rows = (original_len + columns - 1) // columns
    padded_len = rows * columns
    data = list(bits[:padded_len]) + [0] * max(0, padded_len - len(bits))
    matrix = [[0] * columns for _ in range(rows)]
    k = 0
    for c in range(columns):
        for r in range(rows):
            matrix[r][c] = data[k]
            k += 1
    flat = [matrix[r][c] for r in range(rows) for c in range(columns)]
    return flat[:original_len]


def encode_robust(payload: bytes) -> list[int]:
    if not payload or len(payload) > MAX_PAYLOAD:
        raise ValueError(f"Payload must contain 1..{MAX_PAYLOAD} bytes")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = struct.pack(HEADER_FMT, MAGIC, VERSION, len(payload), crc)
    # Keep the fixed header un-interleaved so its size is known at extraction.
    # The payload is Hamming coded and interleaved to spread burst errors.
    header_bits = _hamming_encode(header)
    payload_bits = _hamming_encode(payload)
    return header_bits + _interleave(payload_bits)


def frame_bit_length(payload_length: int) -> int:
    payload_coded = payload_length * 14
    columns = 17
    rows = (payload_coded + columns - 1) // columns
    return HEADER_SIZE * 14 + rows * columns


def decode_header(bits: list[int]) -> tuple[int, int, int, int]:
    """Decode the fixed robust header and return (version, payload_len, crc32, corrected)."""
    header_coded_len = HEADER_SIZE * 14
    if len(bits) < header_coded_len:
        raise ValueError("Robust provenance header is too short")
    header_bytes, corrected, failed = _hamming_decode(bits[:header_coded_len])
    if failed or len(header_bytes) < HEADER_SIZE:
        raise ValueError("Provenance header could not be error-corrected")
    magic, version, payload_len, crc = struct.unpack(HEADER_FMT, header_bytes[:HEADER_SIZE])
    if magic != MAGIC or version != VERSION or not (1 <= payload_len <= MAX_PAYLOAD):
        raise ValueError("No valid Aletheia robust provenance header")
    return version, payload_len, crc, corrected


def decode_robust(bits: list[int]) -> tuple[bytes, dict]:
    """Decode a robust frame and validate magic, version, length and CRC."""
    header_coded_len = HEADER_SIZE * 14
    if len(bits) < header_coded_len:
        raise ValueError("Robust provenance frame is too short")

    header_bytes, corrected_h, failed_h = _hamming_decode(bits[:header_coded_len])
    if failed_h or len(header_bytes) < HEADER_SIZE:
        raise ValueError("Provenance header could not be error-corrected")

    magic, version, payload_len, expected_crc = struct.unpack(
        HEADER_FMT, header_bytes[:HEADER_SIZE]
    )
    if magic != MAGIC or version != VERSION or not (1 <= payload_len <= MAX_PAYLOAD):
        raise ValueError("No valid Aletheia robust provenance header")

    payload_coded = payload_len * 14
    columns = 17
    rows = (payload_coded + columns - 1) // columns
    payload_interleaved_len = rows * columns
    total_len = header_coded_len + payload_interleaved_len
    if len(bits) < total_len:
        raise ValueError("Image does not contain the complete robust provenance frame")

    payload_coded_bits = _deinterleave(
        bits[header_coded_len:total_len], payload_coded, columns=columns
    )
    payload, corrected_p, failed_p = _hamming_decode(payload_coded_bits)
    if failed_p or len(payload) < payload_len:
        raise ValueError("Provenance payload could not be error-corrected")
    payload = payload[:payload_len]
    actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise ValueError("Provenance CRC mismatch")

    return payload, {
        "version": version,
        "corrected_codewords": corrected_h + corrected_p,
        "failed_codewords": failed_h + failed_p,
        "payload_bytes": payload_len,
        "frame_bits": total_len,
    }
