"""
frequency/power_law.py — Natural image power law analysis.

Analyzes whether an image's frequency spectrum adheres to the 1/f^α power law
characteristic of natural photographs.

Scientific Foundation
---------------------
Natural images exhibit a remarkably consistent power spectrum that follows
a power law: P(f) ∝ 1/f^α, where α ≈ 2.0 (pink noise). This property arises
from the scale-invariant statistics of natural scenes.

AI-generated images often deviate from this natural falloff because:
  1. Generators prioritize perceptual quality over statistical naturalness
  2. Training losses (GAN discriminator, diffusion denoising) don't enforce
     frequency-domain naturalness
  3. Convolutional architectures introduce characteristic frequency biases

Reference:
  Torralba & Oliva, "Statistics of natural image categories" (Network 2003).
  Field, "Relations between the statistics of natural images and the response
  properties of cortical cells" (JOSA 1987).

Detection Strategy
------------------
1. Compute radial power spectrum from 2D FFT
2. Fit log(P) = -α * log(f) + c via linear regression
3. Measure R² (goodness-of-fit to power law)
4. Measure deviation of α from natural value (2.0)
5. Low R² or atypical α → suspicion of AI generation

Design
------
* No training required (statistical analysis)
* Depends only on NumPy
* All thresholds are module-level constants
"""
from __future__ import annotations

import numpy as np

from app.services.ai_forensics.frequency.spectral_utils import (
    compute_2d_fft,
    compute_radial_profile,
)


# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

# Natural images: R² > 0.75 (strong adherence to power law)
# AI images: R² < 0.75 (deviation from natural statistics)
_POWER_LAW_R2_THRESHOLD = 0.75

# Natural images: 1.5 < α < 2.5 (typical range)
# AI images: α outside this range
_NATURAL_ALPHA_MIN = 1.5
_NATURAL_ALPHA_MAX = 2.5
_NATURAL_ALPHA_TARGET = 2.0


# ---------------------------------------------------------------------------
# Power law fitting
# ---------------------------------------------------------------------------

def _fit_power_law(radial_profile: np.ndarray) -> tuple[float, float]:
    """
    Fit 1/f^α power law to radial power spectrum.

    Uses linear regression in log-log space:
      log(P) = -α * log(f) + c

    Args:
        radial_profile: 1D radial power spectrum, indexed by frequency.

    Returns:
        (alpha, r_squared) tuple:
          alpha: Power law exponent (natural images ≈ 2.0)
          r_squared: Goodness-of-fit (0 = no fit, 1 = perfect fit)
    """
    # Exclude DC component (f=0) and very low frequencies
    # Start from f=5 to avoid log(0) and DC bias
    start_freq = 5
    if len(radial_profile) <= start_freq:
        # Profile too short
        return 0.0, 0.0

    frequencies = np.arange(start_freq, len(radial_profile))
    power = radial_profile[start_freq:]

    # Filter out zero/negative power values (from numerical issues)
    valid = power > 1e-10
    if valid.sum() < 10:
        # Insufficient valid points
        return 0.0, 0.0

    frequencies = frequencies[valid]
    power = power[valid]

    # Log-log space
    log_f = np.log(frequencies)
    log_p = np.log(power)

    # Linear regression: y = mx + b
    # Here: log(P) = -α * log(f) + c
    n = len(log_f)
    mean_log_f = log_f.mean()
    mean_log_p = log_p.mean()

    # Compute slope (α) and intercept
    numerator = np.sum((log_f - mean_log_f) * (log_p - mean_log_p))
    denominator = np.sum((log_f - mean_log_f) ** 2)

    if denominator < 1e-10:
        return 0.0, 0.0

    slope = numerator / denominator  # This will be negative for 1/f falloff
    alpha = -slope  # Convert to positive exponent

    # Compute R² (coefficient of determination)
    ss_tot = np.sum((log_p - mean_log_p) ** 2)
    predicted_log_p = slope * log_f + (mean_log_p - slope * mean_log_f)
    ss_res = np.sum((log_p - predicted_log_p) ** 2)

    if ss_tot < 1e-10:
        r_squared = 0.0
    else:
        r_squared = 1.0 - (ss_res / ss_tot)
        # Clamp to [0, 1]
        r_squared = max(0.0, min(1.0, r_squared))

    return float(alpha), float(r_squared)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class PowerLawAnalyzer:
    """
    Analyzes frequency spectrum adherence to natural 1/f^α power law.

    analyze(gray) → dict with:
      score       : float in [0, 1] — suspicion of deviation from natural statistics
      confidence  : float in [0, 1]
      features    : diagnostic dict for metadata
      flags       : list[str] of human-readable observations
    """

    def analyze(self, gray: np.ndarray) -> dict:
        """
        Analyze power law statistics of frequency spectrum.

        Args:
            gray: Grayscale image array (H, W), dtype float32.

        Returns:
            dict with keys: score, confidence, features, flags
        """
        # ----------------------------------------------------------------
        # Compute radial power spectrum
        # ----------------------------------------------------------------
        magnitude = compute_2d_fft(gray)
        radial_profile = compute_radial_profile(magnitude)

        if len(radial_profile) < 20:
            # Spectrum too short for reliable fitting
            return {
                "score": 0.0,
                "confidence": 0.0,
                "features": {
                    "power_law_alpha": 0.0,
                    "power_law_r_squared": 0.0,
                    "spectrum_too_short": True,
                },
                "flags": ["Frequency spectrum too short for power law analysis"],
            }

        # ----------------------------------------------------------------
        # Fit 1/f^α power law
        # ----------------------------------------------------------------
        alpha, r_squared = _fit_power_law(radial_profile)

        # ----------------------------------------------------------------
        # Scoring
        # ----------------------------------------------------------------
        raw_score = 0.0
        flags: list[str] = []

        # Check R² (goodness-of-fit)
        if r_squared < _POWER_LAW_R2_THRESHOLD:
            raw_score += 0.60
            flags.append(
                f"Frequency spectrum deviates from natural 1/f^α power law "
                f"(R²={r_squared:.3f} < {_POWER_LAW_R2_THRESHOLD}) — "
                f"power distribution inconsistent with natural photography"
            )

        # Check α (exponent value)
        alpha_deviation = abs(alpha - _NATURAL_ALPHA_TARGET)
        if not (_NATURAL_ALPHA_MIN <= alpha <= _NATURAL_ALPHA_MAX):
            raw_score += 0.40
            flags.append(
                f"Power law exponent α={alpha:.3f} is outside natural range "
                f"[{_NATURAL_ALPHA_MIN}, {_NATURAL_ALPHA_MAX}] — "
                f"frequency falloff atypical for real photographs"
            )

        if not flags:
            flags.append(
                f"Frequency spectrum adheres to natural 1/f^α power law "
                f"(α={alpha:.3f}, R²={r_squared:.3f}) — "
                f"power distribution consistent with natural image statistics"
            )

        score = min(raw_score, 1.0)

        # Confidence based on fit quality
        # High R² → confident in the assessment (whether suspicious or not)
        # Low R² → spectrum is noisy, less confident
        base_confidence = 0.40
        r2_confidence_boost = r_squared * 0.40
        confidence = base_confidence + r2_confidence_boost

        # ----------------------------------------------------------------
        # Features for metadata
        # ----------------------------------------------------------------
        features = {
            "power_law_alpha": round(alpha, 4),
            "power_law_r_squared": round(r_squared, 4),
            "alpha_deviation_from_natural": round(alpha_deviation, 4),
            "natural_alpha_target": _NATURAL_ALPHA_TARGET,
            "within_natural_range": _NATURAL_ALPHA_MIN <= alpha <= _NATURAL_ALPHA_MAX,
        }

        return {
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "features": features,
            "flags": flags,
        }
