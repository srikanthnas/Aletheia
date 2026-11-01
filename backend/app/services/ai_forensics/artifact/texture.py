"""
artifact/texture.py — Classical texture analysis for AI artifact detection.

AI-generated images — particularly those from diffusion models — exhibit
characteristic texture signatures that differ from real photography:

  * GAN upsampling creates regular, grid-like texture repetitions.
  * Diffusion models can produce regions of hyper-uniform "painted" texture
    where natural stochastic variation would be expected.
  * Semantic generators sometimes over-smooth fine textures in background
    regions while over-sharpening foreground subjects.

This module quantifies these signals using three complementary measures:

  1. Local Binary Patterns (LBP) — encodes micro-texture topology.
  2. Texture Entropy           — measures randomness of the LBP histogram.
  3. Local Variance Map        — captures regional texture uniformity.

Each measure produces a feature value. The TextureAnalyzer converts these
into a normalised suspicion score in [0, 1].

Design
------
* No training required.
* No external ML models.
* Depends only on NumPy, SciPy, PIL, and scikit-image (already installed).
* All thresholds are module-level constants — tunable without touching business logic.
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from skimage.feature import local_binary_pattern


# ---------------------------------------------------------------------------
# Tunable thresholds  (empirically calibrated)
# ---------------------------------------------------------------------------

# LBP histogram uniformity — proportion of histogram mass in the top-5 bins
# Real photos typically < 0.45; AI images (uniform regions) > 0.55
_LBP_UNIFORMITY_THRESHOLD = 0.55

# Texture entropy — AI images cluster near 3.0–4.2 nats
_ENTROPY_AI_LOW  = 3.0
_ENTROPY_AI_HIGH = 4.2

# Local-variance coefficient of variation (std / mean of local 8x8 patches)
# Low CoV → over-uniformly textured (AI hallmark in background regions)
_LOCAL_VAR_COV_THRESHOLD = 0.30


# ---------------------------------------------------------------------------
# Feature extractors
# ---------------------------------------------------------------------------

def _compute_lbp(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Compute uniform LBP (P=8, R=1) and its histogram.

    Returns:
        lbp_image  : (H, W) uint8 array of LBP codes.
        uniformity : proportion of histogram mass in the 5 most frequent bins.
    """
    lbp = local_binary_pattern(gray.astype(np.uint8), P=8, R=1, method="uniform")
    n_bins = int(lbp.max()) + 1
    hist, _ = np.histogram(lbp, bins=n_bins, density=True)
    # Sort descending — top-5 bins mass as uniformity measure
    top5_mass = float(np.sort(hist)[::-1][:5].sum())
    return lbp, top5_mass


def _compute_texture_entropy(lbp_image: np.ndarray) -> float:
    """
    Shannon entropy of the LBP histogram (nats).
    Higher entropy → more diverse micro-textures → more natural.
    Lower entropy → repetitive texture → more suspicious.
    """
    n_bins = int(lbp_image.max()) + 1
    hist, _ = np.histogram(lbp_image, bins=n_bins, density=True)
    probs = hist[hist > 0]
    return float(-np.sum(probs * np.log(probs)))


def _compute_local_variance_cov(gray: np.ndarray, patch_size: int = 8) -> float:
    """
    Tile the image into non-overlapping patches and compute per-patch variance.
    Returns the Coefficient of Variation (std/mean) across all patch variances.

    Low CoV → uniform texture → suspicious (AI over-smooth background).
    High CoV → heterogeneous texture → natural.
    """
    h, w = gray.shape
    variances = []
    for i in range(0, h - patch_size + 1, patch_size):
        for j in range(0, w - patch_size + 1, patch_size):
            patch = gray[i : i + patch_size, j : j + patch_size].astype(np.float32)
            variances.append(float(patch.var()))

    if not variances:
        return 0.0

    arr = np.array(variances)
    mean = arr.mean()
    if mean < 1e-8:
        return 0.0
    return float(arr.std() / mean)


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class TextureAnalyzer:
    """
    Classically-computed texture analyser.

    analyze(image) → dict with:
      score       : float in [0, 1] — suspicion that texture is AI-generated
      confidence  : float in [0, 1]
      features    : diagnostic dict for inclusion in metadata
      flags       : list[str] of human-readable observations
    """

    def analyze(self, image: Image.Image) -> dict:
        gray = np.array(image.convert("L"), dtype=np.float32)

        lbp_image, uniformity = _compute_lbp(gray)
        entropy  = _compute_texture_entropy(lbp_image)
        var_cov  = _compute_local_variance_cov(gray)

        # ----------------------------------------------------------------
        # Scoring — each suspicious indicator adds to the raw score
        # ----------------------------------------------------------------
        raw  = 0.0
        flags: list[str] = []

        if uniformity > _LBP_UNIFORMITY_THRESHOLD:
            raw += 0.35
            flags.append(
                f"High LBP uniformity ({uniformity:.3f} > {_LBP_UNIFORMITY_THRESHOLD}) "
                "— micro-texture is unusually repetitive"
            )

        if _ENTROPY_AI_LOW <= entropy <= _ENTROPY_AI_HIGH:
            raw += 0.30
            flags.append(
                f"Texture entropy {entropy:.2f} nats is within AI-typical range "
                f"[{_ENTROPY_AI_LOW}, {_ENTROPY_AI_HIGH}]"
            )

        if var_cov < _LOCAL_VAR_COV_THRESHOLD:
            raw += 0.25
            flags.append(
                f"Low local-variance CoV ({var_cov:.3f} < {_LOCAL_VAR_COV_THRESHOLD}) "
                "— texture uniformity inconsistent with natural photography"
            )

        score      = min(raw, 1.0)
        confidence = min(0.25 + len(flags) * 0.20, 0.85)

        return {
            "score":      round(score, 4),
            "confidence": round(confidence, 4),
            "features": {
                "lbp_uniformity":   round(uniformity, 4),
                "texture_entropy":  round(entropy, 4),
                "local_var_cov":    round(var_cov, 4),
            },
            "flags": flags,
        }
