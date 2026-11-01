"""
frequency/compression_forensics.py — JPEG compression fingerprint analysis.

Analyzes 8×8 block boundary discontinuities to detect the presence or absence
of authentic JPEG compression artifacts.

Scientific Foundation
---------------------
Most digital camera photos are saved as JPEG, which uses 8×8 DCT block
quantization. This process introduces perceptible discontinuities at block
boundaries (the "blocky" artifact visible at low JPEG quality).

Even high-quality JPEG images (Q=90+) exhibit measurable block boundary
variance that differs from within-block variance. This fingerprint persists
even after subsequent lossless conversions (JPEG → PNG).

AI-generated images are typically exported as PNG (lossless) and have never
undergone JPEG compression. They exhibit smooth transitions across 8×8 block
boundaries, with boundary_var / within_var ≈ 1.0.

Reference:
  Popescu & Farid, "Exposing digital forgeries by detecting traces of
  resampling" (IEEE Trans. on Signal Processing 2005).
  
  Fan & de Queiroz, "Identification of bitmap compression history"
  (IEEE ICASSP 2003).

Detection Strategy
------------------
1. Partition image into 8×8 blocks (JPEG DCT grid)
2. Measure variance across block boundaries
3. Measure variance within each block (excluding boundaries)
4. Compute ratio = boundary_var / within_var
5. Real JPEG: ratio > 1.5
   AI PNG: ratio ≈ 1.0

Limitations
-----------
* High-end cameras shooting RAW → converted to PNG also lack JPEG fingerprint
  (This is expected behavior — absence of JPEG is suspicious for consumer
  photos but normal for professional photography)
* AI image → saved as JPEG → now has compression artifacts
  (Mitigated by other frequency detectors: grid patterns, power law)

Design
------
* No training required (statistical analysis)
* Depends only on NumPy
* All thresholds are module-level constants
"""
from __future__ import annotations

import numpy as np

from app.services.ai_forensics.frequency.spectral_utils import (
    compute_block_boundary_ratio,
)


# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

# Real JPEG photos: boundary_ratio > 1.5 (strong discontinuity)
# AI PNG exports: boundary_ratio ≈ 1.0 (smooth)
_JPEG_BOUNDARY_RATIO_STRONG = 1.5   # Definitive JPEG fingerprint
_JPEG_BOUNDARY_RATIO_WEAK = 1.3     # Weak JPEG fingerprint

# Minimum image dimension for reliable block analysis
_MIN_IMAGE_SIZE = 64  # At least 8×8 blocks needed


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class CompressionForensicsAnalyzer:
    """
    Analyzes JPEG compression fingerprints via block boundary discontinuities.

    analyze(gray) → dict with:
      score       : float in [0, 1] — suspicion of no compression history
      confidence  : float in [0, 1]
      features    : diagnostic dict for metadata
      flags       : list[str] of human-readable observations
    """

    def analyze(self, gray: np.ndarray) -> dict:
        """
        Analyze JPEG block boundary discontinuities.

        Args:
            gray: Grayscale image array (H, W), dtype float32.

        Returns:
            dict with keys: score, confidence, features, flags
        """
        h, w = gray.shape

        # ----------------------------------------------------------------
        # Edge case: image too small
        # ----------------------------------------------------------------
        if min(h, w) < _MIN_IMAGE_SIZE:
            return {
                "score": 0.0,
                "confidence": 0.0,
                "features": {
                    "block_boundary_ratio": 1.0,
                    "image_too_small": True,
                    "min_dimension": min(h, w),
                },
                "flags": [
                    f"Image too small ({min(h, w)} < {_MIN_IMAGE_SIZE}) for "
                    "reliable DCT block boundary analysis"
                ],
            }

        # ----------------------------------------------------------------
        # Compute block boundary ratio
        # ----------------------------------------------------------------
        boundary_ratio = compute_block_boundary_ratio(gray, block_size=8)

        # ----------------------------------------------------------------
        # Scoring
        # ----------------------------------------------------------------
        raw_score = 0.0
        flags: list[str] = []

        if boundary_ratio < _JPEG_BOUNDARY_RATIO_WEAK:
            # Strong evidence of no JPEG compression
            if boundary_ratio < 1.1:
                raw_score = 0.80
                confidence = 0.85
                flags.append(
                    f"Very smooth 8×8 block boundaries (ratio={boundary_ratio:.3f} ≈ 1.0) — "
                    f"image lacks JPEG compression fingerprint. Typical of AI PNG exports "
                    f"or uncompressed camera RAW conversions."
                )
            else:
                raw_score = 0.50
                confidence = 0.70
                flags.append(
                    f"Low block boundary discontinuity (ratio={boundary_ratio:.3f} < "
                    f"{_JPEG_BOUNDARY_RATIO_WEAK}) — weak JPEG compression fingerprint. "
                    f"May be AI-generated PNG or high-quality JPEG (Q>95)."
                )
        elif boundary_ratio < _JPEG_BOUNDARY_RATIO_STRONG:
            # Ambiguous — could be high-quality JPEG or AI with added noise
            raw_score = 0.20
            confidence = 0.50
            flags.append(
                f"Moderate block boundary discontinuity (ratio={boundary_ratio:.3f}) — "
                f"ambiguous JPEG fingerprint. Could be high-quality JPEG or "
                f"AI image with post-processing."
            )
        else:
            # Strong JPEG fingerprint → likely real photo
            raw_score = 0.0
            confidence = 0.80
            flags.append(
                f"Strong block boundary discontinuity (ratio={boundary_ratio:.3f} > "
                f"{_JPEG_BOUNDARY_RATIO_STRONG}) — definitive JPEG compression "
                f"fingerprint present. Consistent with authentic camera photo."
            )

        score = min(raw_score, 1.0)

        # ----------------------------------------------------------------
        # Features for metadata
        # ----------------------------------------------------------------
        features = {
            "block_boundary_ratio": round(boundary_ratio, 4),
            "jpeg_fingerprint_detected": boundary_ratio >= _JPEG_BOUNDARY_RATIO_STRONG,
            "weak_fingerprint": (
                _JPEG_BOUNDARY_RATIO_WEAK <= boundary_ratio < _JPEG_BOUNDARY_RATIO_STRONG
            ),
            "no_fingerprint": boundary_ratio < _JPEG_BOUNDARY_RATIO_WEAK,
        }

        return {
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "features": features,
            "flags": flags,
        }
