"""
hamming_distance.py — Hamming Distance computation and verification verdict.

All thresholds are module-level constants. To change sensitivity, edit ONLY
this file — no other module needs touching.

64-bit pHash max Hamming Distance = 64.
"""

import imagehash

from app.services.verification.phash_service import MAX_HASH_BITS

# ---------------------------------------------------------------------------
# Configurable thresholds (Hamming Distance upper bounds, inclusive)
# ---------------------------------------------------------------------------

THRESHOLD_AUTHENTIC          = 5   # 0–5   → AUTHENTIC
THRESHOLD_MINOR_MODIFICATION = 10  # 6–10  → MINOR MODIFICATION
THRESHOLD_MODIFIED           = 20  # 11–20 → MODIFIED
# > 20                               → UNVERIFIED

VERDICT_AUTHENTIC          = "AUTHENTIC"
VERDICT_MINOR_MODIFICATION = "MINOR MODIFICATION"
VERDICT_MODIFIED           = "MODIFIED"
VERDICT_UNVERIFIED         = "UNVERIFIED"


def compute_hamming_distance(hash_hex_a: str, hash_hex_b: str) -> int:
    """
    Compute Hamming Distance between two 64-bit pHash hex strings.

    Returns:
        int — 0 (identical) to 64 (completely different).

    Raises:
        ValueError: If either hex string is invalid.
    """
    try:
        ha = imagehash.hex_to_hash(hash_hex_a)
        hb = imagehash.hex_to_hash(hash_hex_b)
        return int(ha - hb)
    except Exception as exc:
        raise ValueError(f"Hamming Distance computation failed: {exc}") from exc


def compute_similarity(distance: int) -> float:
    """
    Convert Hamming Distance to a similarity percentage.

    similarity = (1 - distance / MAX_HASH_BITS) * 100

    Returns:
        float — 0.0–100.0, rounded to 2 decimal places.
    """
    if distance < 0 or distance > MAX_HASH_BITS:
        raise ValueError(
            f"Distance {distance} out of range [0, {MAX_HASH_BITS}]."
        )
    return round((1.0 - distance / MAX_HASH_BITS) * 100.0, 2)


def get_verification_verdict(distance: int) -> str:
    """
    Map Hamming Distance to a human-readable verification verdict.

    Uses module-level threshold constants exclusively.

    Returns:
        One of: AUTHENTIC | MINOR MODIFICATION | MODIFIED | UNVERIFIED
    """
    if distance <= THRESHOLD_AUTHENTIC:
        return VERDICT_AUTHENTIC
    if distance <= THRESHOLD_MINOR_MODIFICATION:
        return VERDICT_MINOR_MODIFICATION
    if distance <= THRESHOLD_MODIFIED:
        return VERDICT_MODIFIED
    return VERDICT_UNVERIFIED
