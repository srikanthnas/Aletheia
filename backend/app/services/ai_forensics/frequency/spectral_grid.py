"""
frequency/spectral_grid.py — Spectral grid pattern detection for GAN artifacts.

Detects checkerboard upsampling artifacts produced by transposed convolution
layers in GAN generators. These artifacts are invisible in spatial domain
but manifest as regular spectral peaks in the 2D FFT.

Scientific Foundation
---------------------
GAN generators (StyleGAN, ProGAN, DCGAN) use transposed convolutions for
upsampling. This operation creates periodic grid artifacts in the generated
image. In the frequency domain, these grids appear as bright peaks at
regular intervals (f/2, f/4, f/8) corresponding to the upsampling stages.

Reference:
  Zhang et al., "CNN-generated images are surprisingly easy to spot...for now"
  CVPR 2019. Demonstrates FFT-based detection of upsampling artifacts.

Detection Strategy
------------------
1. Compute 2D FFT magnitude spectrum (DC centered)
2. Sample power at expected grid frequencies (f/2, f/4, f/8)
3. Compare against background spectral power
4. High amplitude at grid frequencies → suspicion of GAN generation

Design
------
* No training required (rule-based)
* Depends only on NumPy FFT
* All thresholds are module-level constants
"""
from __future__ import annotations

import numpy as np

from app.services.ai_forensics.frequency.spectral_utils import compute_2d_fft


# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

# Grid peak amplitude threshold (relative to mean spectral power)
# GAN artifacts produce peaks 2-5× stronger than background
_GRID_PEAK_AMPLITUDE_THRESHOLD = 2.0

# Minimum image size for reliable grid detection
# FFT analysis requires sufficient resolution
_MIN_IMAGE_SIZE = 128


# ---------------------------------------------------------------------------
# Grid detection
# ---------------------------------------------------------------------------

def _measure_peak_at_frequency(
    magnitude: np.ndarray,
    center: tuple[int, int],
    frequency: int,
    sample_radius: int = 3,
) -> float:
    """
    Measure spectral power at a specific frequency distance from DC.

    Samples a circular region around the expected frequency and computes
    the mean magnitude. GAN grids produce localized peaks at these frequencies.

    Args:
        magnitude: 2D FFT magnitude spectrum, DC centered.
        center: (y, x) coordinates of DC component.
        frequency: Radial distance from DC to sample (in pixels).
        sample_radius: Radius of sampling region (default 3 pixels).

    Returns:
        Mean magnitude in the sampling region.
    """
    cy, cx = center
    h, w = magnitude.shape

    # Sample points on a circle of radius `frequency`
    angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    samples = []

    for angle in angles:
        # Compute point on circle
        y = int(cy + frequency * np.sin(angle))
        x = int(cx + frequency * np.cos(angle))

        # Sample neighborhood
        for dy in range(-sample_radius, sample_radius + 1):
            for dx in range(-sample_radius, sample_radius + 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    samples.append(magnitude[ny, nx])

    if not samples:
        return 0.0

    return float(np.mean(samples))


def _compute_background_power(magnitude: np.ndarray) -> float:
    """
    Compute baseline spectral power (excluding DC and very low frequencies).

    Provides a reference for determining if a peak is anomalously high.

    Args:
        magnitude: 2D FFT magnitude spectrum.

    Returns:
        Mean magnitude of mid-frequency components.
    """
    h, w = magnitude.shape
    center = (h // 2, w // 2)

    # Mask out DC and very low frequencies (inner 10% of spectrum)
    y, x = np.ogrid[:h, :w]
    r = np.sqrt((x - center[1]) ** 2 + (y - center[0]) ** 2)
    min_radius = min(h, w) // 10
    mid_freq_mask = r > min_radius

    return float(magnitude[mid_freq_mask].mean())


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class SpectralGridAnalyzer:
    """
    Detects GAN upsampling grid artifacts via FFT analysis.

    analyze(gray) → dict with:
      score       : float in [0, 1] — suspicion that grids are present
      confidence  : float in [0, 1]
      features    : diagnostic dict for metadata
      flags       : list[str] of human-readable observations
    """

    def analyze(self, gray: np.ndarray) -> dict:
        """
        Analyze grayscale image for spectral grid patterns.

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
                    "grid_detected": False,
                    "image_too_small": True,
                    "min_dimension": min(h, w),
                },
                "flags": [
                    f"Image too small ({min(h, w)} < {_MIN_IMAGE_SIZE}) for "
                    "reliable FFT grid detection"
                ],
            }

        # ----------------------------------------------------------------
        # Compute FFT
        # ----------------------------------------------------------------
        magnitude = compute_2d_fft(gray)
        center = (h // 2, w // 2)
        background_power = _compute_background_power(magnitude)

        # ----------------------------------------------------------------
        # Check for peaks at GAN upsampling frequencies
        # Transposed convolution creates peaks at f/2, f/4, f/8
        # ----------------------------------------------------------------
        max_radius = min(center[0], center[1])
        grid_frequencies = [max_radius // d for d in [2, 4, 8] if max_radius // d > 10]

        peak_amplitudes = []
        detected_peaks = 0

        for freq in grid_frequencies:
            peak_power = _measure_peak_at_frequency(magnitude, center, freq)
            peak_amplitudes.append(peak_power)

            # Normalize by background power
            if background_power > 0:
                relative_amplitude = peak_power / background_power
            else:
                relative_amplitude = 0.0

            if relative_amplitude > _GRID_PEAK_AMPLITUDE_THRESHOLD:
                detected_peaks += 1

        # ----------------------------------------------------------------
        # Scoring
        # ----------------------------------------------------------------
        raw_score = 0.0
        flags: list[str] = []

        if detected_peaks >= 2:
            # Multiple grid frequencies detected → strong GAN signal
            raw_score = 0.80
            flags.append(
                f"Detected spectral peaks at {detected_peaks} GAN upsampling "
                f"frequencies (f/2, f/4, f/8) — characteristic of transposed "
                f"convolution checkerboard artifacts"
            )
        elif detected_peaks == 1:
            # Single grid frequency → moderate suspicion
            raw_score = 0.50
            flags.append(
                "Detected spectral peak at one GAN upsampling frequency — "
                "possible transposed convolution artifact"
            )
        else:
            # No grid patterns detected
            flags.append(
                "No significant spectral grid patterns detected — "
                "FFT spectrum is consistent with natural image upsampling"
            )

        score = min(raw_score, 1.0)
        confidence = 0.70 if detected_peaks > 0 else 0.50

        # ----------------------------------------------------------------
        # Features for metadata
        # ----------------------------------------------------------------
        features = {
            "grid_detected": detected_peaks > 0,
            "num_peaks_detected": detected_peaks,
            "grid_frequencies_checked": grid_frequencies,
            "peak_amplitudes": [round(p, 4) for p in peak_amplitudes],
            "background_power": round(background_power, 4),
            "relative_peak_strength": (
                round(max(peak_amplitudes) / background_power, 4)
                if background_power > 0 and peak_amplitudes
                else 0.0
            ),
        }

        return {
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "features": features,
            "flags": flags,
        }
