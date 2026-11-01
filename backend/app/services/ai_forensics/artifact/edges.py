"""
artifact/edges.py — Classical edge analysis for AI artifact detection.

AI-generated images have characteristic edge signatures:

  * Diffusion models (Stable Diffusion, Midjourney) over-smooth mid-frequency
    edges, producing fewer but perfectly-continuous edge contours.
  * GAN generators produce irregular edge maps with small, fragmented segments
    from checkerboard upsampling artifacts.
  * Real photographs have structured, hierarchically-organised edges driven by
    natural depth-of-field, lighting gradients, and object boundaries.

This module quantifies these signals using four measures:

  1. Canny Edge Density   — ratio of edge pixels to total pixels.
  2. Laplacian Variance   — global sharpness / focus consistency.
  3. Edge Continuity      — mean length of connected edge segments.
  4. Edge Strength Std    — standard deviation of edge response magnitudes.

Each measure produces a feature value. The EdgeAnalyzer converts these into
a normalised suspicion score in [0, 1].

Design
------
* No training required.
* Depends only on NumPy, SciPy, PIL, and scikit-image (already installed).
* All thresholds are module-level constants.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import label, laplace
from skimage.feature import canny


# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

# Canny edge density: AI images are frequently over-smooth (< 0.04)
# or GAN-checkerboarded (> 0.22)
_EDGE_DENSITY_LOW  = 0.04
_EDGE_DENSITY_HIGH = 0.22

# Laplacian variance: hyper-sharp foreground + over-smooth background
# leads to an extreme global value
_LAP_VAR_LOW  = 30.0     # suspiciously blurry overall
_LAP_VAR_HIGH = 2500.0   # unrealistically sharp / edge-compressed

# Edge continuity: mean connected-segment length in pixels.
# AI over-smooth edges → very long continuous contours (> 18 px mean).
# GAN checkerboard     → very short fragmented contours (< 4 px mean).
_CONTINUITY_HIGH = 18.0
_CONTINUITY_LOW  =  4.0

# Edge strength standard deviation: GAN/diffusion produce atypically uniform
# edge magnitudes (low std means most edges look the same strength)
_STRENGTH_STD_LOW = 15.0


# ---------------------------------------------------------------------------
# Feature extractors
# ---------------------------------------------------------------------------

def _compute_canny_density(gray_arr: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Run Canny edge detection and compute the edge-pixel ratio.
    Returns (edge_map bool array, density float).
    """
    # Normalise to [0, 1] for skimage.feature.canny
    norm = gray_arr / 255.0
    edges = canny(norm, sigma=1.5, low_threshold=0.05, high_threshold=0.15)
    density = float(edges.sum() / edges.size)
    return edges, density


def _compute_laplacian_variance(gray_arr: np.ndarray) -> float:
    """Variance of the Laplacian response — measures focus / sharpness."""
    lap = laplace(gray_arr.astype(np.float32))
    return float(lap.var())


def _compute_edge_continuity(edge_map: np.ndarray) -> float:
    """
    Compute mean connected-edge-segment length by labelling connected
    components in the Canny edge map.

    Returns mean segment length in pixels (0.0 if no edges found).
    """
    labeled, num_features = label(edge_map)
    if num_features == 0:
        return 0.0
    
    # Use bincount for O(N) performance instead of O(N*K) list comprehension
    # sizes[0] is the background, sizes[1:] are the features
    sizes = np.bincount(labeled.ravel())[1:]
    return float(sizes.mean()) if sizes.size > 0 else 0.0


def _compute_edge_strength_std(gray_arr: np.ndarray) -> float:
    """
    Standard deviation of Sobel edge response magnitudes.

    A very low std means all edges are roughly the same strength — unusual
    in real photography where edge strength varies with depth, lighting, and
    material differences.
    """
    float_arr = gray_arr.astype(np.float32)

    # Finite-difference Sobel approximation without scipy.ndimage dependency
    from scipy.ndimage import sobel as scipy_sobel
    sx = scipy_sobel(float_arr, axis=1)
    sy = scipy_sobel(float_arr, axis=0)
    magnitude = np.hypot(sx, sy)
    return float(magnitude.std())


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class EdgeAnalyzer:
    """
    Classically-computed edge analyser.

    analyze(image) → dict with:
      score       : float in [0, 1] — suspicion that edges are AI-generated
      confidence  : float in [0, 1]
      features    : diagnostic dict for inclusion in metadata
      flags       : list[str] of human-readable observations
    """

    def analyze(self, image: Image.Image) -> dict:
        gray_arr = np.array(image.convert("L"), dtype=np.float32)

        edge_map, density  = _compute_canny_density(gray_arr)
        lap_var            = _compute_laplacian_variance(gray_arr)
        continuity         = _compute_edge_continuity(edge_map)
        strength_std       = _compute_edge_strength_std(gray_arr)

        # ----------------------------------------------------------------
        # Scoring
        # ----------------------------------------------------------------
        raw  = 0.0
        flags: list[str] = []

        # Edge density anomaly
        if density < _EDGE_DENSITY_LOW:
            raw += 0.30
            flags.append(
                f"Very low edge density ({density:.3f} < {_EDGE_DENSITY_LOW}) "
                "— image is over-smooth, typical of diffusion generators"
            )
        elif density > _EDGE_DENSITY_HIGH:
            raw += 0.20
            flags.append(
                f"High edge density ({density:.3f} > {_EDGE_DENSITY_HIGH}) "
                "— fragmented edges suggestive of GAN checkerboard artifacts"
            )

        # Laplacian variance anomaly
        if lap_var < _LAP_VAR_LOW:
            raw += 0.20
            flags.append(
                f"Low Laplacian variance ({lap_var:.1f} < {_LAP_VAR_LOW}) "
                "— globally blurry, not typical of real camera optics"
            )
        elif lap_var > _LAP_VAR_HIGH:
            raw += 0.15
            flags.append(
                f"Extreme Laplacian variance ({lap_var:.1f} > {_LAP_VAR_HIGH}) "
                "— unrealistic sharpness profile"
            )

        # Edge continuity anomaly
        if continuity > _CONTINUITY_HIGH:
            raw += 0.25
            flags.append(
                f"High edge continuity ({continuity:.1f} px mean) "
                "— unnaturally long, smooth contours typical of diffusion outputs"
            )
        elif 0 < continuity < _CONTINUITY_LOW:
            raw += 0.15
            flags.append(
                f"Very short edge segments ({continuity:.1f} px mean) "
                "— highly fragmented edges typical of GAN upsampling"
            )

        # Edge strength uniformity
        if strength_std < _STRENGTH_STD_LOW:
            raw += 0.20
            flags.append(
                f"Low edge-strength std ({strength_std:.1f} < {_STRENGTH_STD_LOW}) "
                "— unnaturally uniform edge magnitudes"
            )

        score      = min(raw, 1.0)
        confidence = min(0.25 + len(flags) * 0.18, 0.88)

        return {
            "score":      round(score, 4),
            "confidence": round(confidence, 4),
            "features": {
                "canny_edge_density":  round(density, 4),
                "laplacian_variance":  round(lap_var, 2),
                "mean_segment_length": round(continuity, 2),
                "edge_strength_std":   round(strength_std, 2),
            },
            "flags": flags,
        }
