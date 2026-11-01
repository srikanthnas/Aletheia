"""
phash_service.py — Perceptual Hash generation.

Generates a 64-bit DCT-based perceptual hash (pHash) for a given image.
Two visually similar images produce near-identical hashes; structural
modifications result in larger Hamming Distances.

LSB steganography changes pixel values by at most ±1, so the pHash of an
embedded image is essentially identical to the original — typically Hamming
Distance 0.

Sprint 5 can extend this to support alternative hash algorithms (aHash, dHash,
wHash) by adding new generate_*() functions without modifying this one.
"""

import imagehash
from PIL import Image

# 8×8 DCT grid → 64-bit hash
HASH_SIZE:     int = 8
MAX_HASH_BITS: int = HASH_SIZE * HASH_SIZE  # 64


def generate_phash(image: Image.Image) -> str:
    """
    Generate a 64-bit perceptual hash for the image.

    Args:
        image: PIL Image (any mode; converted internally by imagehash).

    Returns:
        str — 16-character lowercase hex string, e.g. 'a3b4c5d6e7f80192'.

    Raises:
        ValueError: If the image cannot be processed.
    """
    try:
        ph = imagehash.phash(image, hash_size=HASH_SIZE)
        return str(ph)
    except Exception as exc:
        raise ValueError(f"Failed to generate pHash: {exc}") from exc
