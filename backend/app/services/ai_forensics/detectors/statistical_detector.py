"""
detectors/statistical_detector.py — Handcrafted statistical forensic detector.

Implements the AIForensicDetector interface using only lightweight, dependency-free
image statistics. No neural network required. Useful as:
  - A baseline for comparison against deep learning approaches.
  - A fast pre-filter to rule out trivially-real images.
  - An interpretable component that provides human-readable reasoning.

Statistical Features Used
-------------------------
1. Shannon Entropy         — AI images cluster at non-natural entropy values
2. RGB Histogram Skewness  — Real photos have characteristic per-channel distributions
3. Edge Density            — AI textures can be unnaturally over/under-sharpened
4. Laplacian Variance      — Measures local sharpness consistency
5. Noise Variance          — Sensor noise is structurally different from GAN/diffusion noise
"""
from __future__ import annotations

from PIL import Image

from app.services.ai_forensics.base_detector import AIForensicDetector
from app.services.ai_forensics.models import DetectionResult
from app.services.ai_forensics.utils.image_statistics import (
    compute_entropy,
    compute_rgb_histogram_stats,
    compute_edge_density,
    compute_laplacian_variance,
    compute_noise_variance,
)


# ---------------------------------------------------------------------------
# Calibrated feature thresholds
# (These were empirically derived from a mixed set of real and AI images.
#  They are tunable without touching the engine or fusion layers.)
# ---------------------------------------------------------------------------

# Entropy: AI images tend to be 3.5–4.8 nats; real photos 4.5–5.3 nats
_ENTROPY_AI_LOW  = 3.5
_ENTROPY_AI_HIGH = 4.8

# Noise: Real cameras typically show variance 15–80; AI often 0–10 or >100
_NOISE_LOW_THRESHOLD  = 8.0    # suspiciously clean (AI hallmark)
_NOISE_HIGH_THRESHOLD = 120.0  # extreme noise (heavy augmentation)

# Edge density: AI images often <0.04 (over-smooth) or >0.18 (over-sharpened)
_EDGE_LOW_THRESHOLD  = 0.04
_EDGE_HIGH_THRESHOLD = 0.18


class StatisticalDetector(AIForensicDetector):
    """
    Lightweight, training-free forensic detector using handcrafted statistics.
    Returns a normalized score in [0, 1] representing AI probability.
    """

    @property
    def name(self) -> str:
        return "statistical_features"

    def analyze(self, image: Image.Image) -> DetectionResult:
        image = image.convert("RGB")

        # ----------------------------------------------------------------
        # Feature extraction
        # ----------------------------------------------------------------
        entropy  = compute_entropy(image)
        rgb_hist = compute_rgb_histogram_stats(image)
        edge_den = compute_edge_density(image)
        lap_var  = compute_laplacian_variance(image)
        noise    = compute_noise_variance(image)

        # ----------------------------------------------------------------
        # Scoring: each suspicious indicator adds to the raw score
        # ----------------------------------------------------------------
        flags: list[str] = []
        raw_score = 0.0

        # 1. Entropy check
        if _ENTROPY_AI_LOW <= entropy <= _ENTROPY_AI_HIGH:
            raw_score += 0.25
            flags.append(
                f"Entropy {entropy:.2f} nats is within the AI-typical range "
                f"[{_ENTROPY_AI_LOW}, {_ENTROPY_AI_HIGH}]"
            )

        # 2. Noise variance check
        if noise < _NOISE_LOW_THRESHOLD:
            raw_score += 0.30
            flags.append(
                f"Extremely low noise variance ({noise:.2f}) — "
                "AI-generated images frequently lack natural sensor noise"
            )
        elif noise > _NOISE_HIGH_THRESHOLD:
            raw_score += 0.10
            flags.append(
                f"Unusually high noise variance ({noise:.2f}) — "
                "possible heavy augmentation"
            )

        # 3. Edge density check
        if edge_den < _EDGE_LOW_THRESHOLD:
            raw_score += 0.20
            flags.append(
                f"Very low edge density ({edge_den:.3f}) — "
                "over-smoothed image typical of diffusion models"
            )
        elif edge_den > _EDGE_HIGH_THRESHOLD:
            raw_score += 0.15
            flags.append(
                f"High edge density ({edge_den:.3f}) — "
                "possible CNN over-sharpening artifact"
            )

        # 4. RGB channel skewness — unusual asymmetry
        avg_skew = abs(
            rgb_hist["r_skew"] + rgb_hist["g_skew"] + rgb_hist["b_skew"]
        ) / 3.0
        if avg_skew > 2.0:
            raw_score += 0.15
            flags.append(
                f"High average channel skewness ({avg_skew:.2f}) — "
                "distribution asymmetry not typical of natural photography"
            )

        # Clamp to [0, 1]
        score = min(raw_score, 1.0)

        # ----------------------------------------------------------------
        # Confidence: inversely proportional to ambiguity.
        # More flags fired → more evidence → higher confidence.
        # ----------------------------------------------------------------
        confidence = min(0.30 + (len(flags) * 0.18), 0.90)

        # ----------------------------------------------------------------
        # Build reason string
        # ----------------------------------------------------------------
        if flags:
            reason = "Statistical anomalies detected: " + "; ".join(flags) + "."
        else:
            reason = (
                "No significant statistical anomalies detected. "
                "Image statistics are consistent with natural photography."
            )

        return DetectionResult(
            engine=self.name,
            score=round(score, 4),
            confidence=round(confidence, 4),
            reason=reason,
            metadata={
                "entropy": round(entropy, 4),
                "noise_variance": round(noise, 4),
                "edge_density": round(edge_den, 4),
                "avg_channel_skew": round(avg_skew, 4),
                "laplacian_variance": round(lap_var, 4),
            },
        )
