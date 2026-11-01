"""Exact pixel-level integrity fingerprinting.

This fingerprint is intentionally sensitive to post-embedding edits.  Unlike
pHash, it is NOT invariant to brightness/contrast changes.  Aletheia uses it
alongside pHash:

* pixel hash -> exact identity of the registered embedded pixels
* pHash      -> perceptual/robust similarity

The combination lets the system distinguish an untouched embedded image from
an image that still contains a valid watermark but was subsequently changed.
"""

from __future__ import annotations

import hashlib
from PIL import Image


def generate_pixel_hash(image: Image.Image) -> str:
    """Return a SHA-256 fingerprint of the decoded RGB pixel matrix."""
    try:
        rgb = image.convert("RGB")
        header = f"RGB:{rgb.width}x{rgb.height}:".encode("ascii")
        return hashlib.sha256(header + rgb.tobytes()).hexdigest()
    except Exception as exc:
        raise ValueError(f"Failed to generate pixel integrity hash: {exc}") from exc
