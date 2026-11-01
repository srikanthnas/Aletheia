"""
app/services/verification/__init__.py — Public surface of the verification package.
"""

from app.services.verification.phash_service import generate_phash, HASH_SIZE, MAX_HASH_BITS
from app.services.verification.hamming_distance import (
    compute_hamming_distance,
    compute_similarity,
    get_verification_verdict,
    THRESHOLD_AUTHENTIC,
    THRESHOLD_MINOR_MODIFICATION,
    THRESHOLD_MODIFIED,
    VERDICT_AUTHENTIC,
    VERDICT_MINOR_MODIFICATION,
    VERDICT_MODIFIED,
    VERDICT_UNVERIFIED,
)
from app.services.verification.verification_service import (
    verify_provenance,
    VerificationResult,
)

__all__ = [
    "generate_phash",
    "HASH_SIZE",
    "MAX_HASH_BITS",
    "compute_hamming_distance",
    "compute_similarity",
    "get_verification_verdict",
    "THRESHOLD_AUTHENTIC",
    "THRESHOLD_MINOR_MODIFICATION",
    "THRESHOLD_MODIFIED",
    "VERDICT_AUTHENTIC",
    "VERDICT_MINOR_MODIFICATION",
    "VERDICT_MODIFIED",
    "VERDICT_UNVERIFIED",
    "verify_provenance",
    "VerificationResult",
]
