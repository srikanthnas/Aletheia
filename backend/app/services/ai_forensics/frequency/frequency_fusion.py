"""
frequency/frequency_fusion.py — Weighted fusion for frequency analyzers.

Combines spectral grid, power law, and compression forensics results into
a single unified score and explanation.

Design
------
Mirrors the architecture of artifact/fusion.py exactly:
  * Weights are injected (not hardcoded in analyzers)
  * Unknown analyzer names receive default weight
  * Produces unified (score, confidence, explanation) triple
  * Flags are aggregated with weight annotations

Weight Philosophy
-----------------
Each analyzer provides orthogonal evidence:
  * Grid detection: GAN upsampling artifacts (strongest signal for GANs)
  * Power law: Natural image statistics (fundamental property)
  * Compression: JPEG fingerprint (separates camera from AI exports)

Default weights reflect expected discriminative power:
  * Grid: 0.40 (definitive when present, but generator-specific)
  * Power law: 0.30 (universal but can be noisy)
  * Compression: 0.30 (strong but legitimate edge cases exist)

These weights are tunable and should be calibrated on a labeled dataset.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Default weights (tunable — calibrate on labeled dataset)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "grid": 0.40,        # Spectral grid patterns (GAN upsampling)
    "power_law": 0.30,   # 1/f^α power law deviation
    "compression": 0.30, # JPEG block boundary analysis
}

DEFAULT_WEIGHT = 0.33  # Fallback for unknown analyzers


# ---------------------------------------------------------------------------
# Fusion logic
# ---------------------------------------------------------------------------

class FrequencyFusion:
    """
    Weighted-average combiner for frequency-domain analyzer outputs.

    Each analyzer returns a dict: {score, confidence, flags, features}.
    FrequencyFusion produces a single (score, confidence, explanation) triple
    consumed by FrequencyDetector → DetectionResult.

    Usage::

        fusion = FrequencyFusion()
        result = fusion.combine(grid_result, power_result, comp_result)

    Custom weights::

        fusion = FrequencyFusion(weights={"grid": 0.50, "power_law": 0.30, "compression": 0.20})
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        default_weight: float = DEFAULT_WEIGHT,
    ) -> None:
        """
        Initialize fusion with configurable weights.

        Args:
            weights: Dict mapping analyzer names to weights.
                     If None, uses DEFAULT_WEIGHTS.
            default_weight: Fallback weight for unknown analyzers.
        """
        self._weights = weights if weights is not None else DEFAULT_WEIGHTS
        self._default_weight = default_weight

    def combine(
        self,
        grid_result: dict,
        power_result: dict,
        comp_result: dict,
    ) -> dict[str, object]:
        """
        Combine three analyzer results into a unified score.

        Args:
            grid_result: Output dict from SpectralGridAnalyzer.analyze()
            power_result: Output dict from PowerLawAnalyzer.analyze()
            comp_result: Output dict from CompressionForensicsAnalyzer.analyze()

        Returns:
            dict with keys: score, confidence, explanation, features
        """
        # Map analyzer names to results
        named_results = {
            "grid": grid_result,
            "power_law": power_result,
            "compression": comp_result,
        }

        # ----------------------------------------------------------------
        # Weighted average of scores and confidences
        # ----------------------------------------------------------------
        total_w = 0.0
        w_score = 0.0
        w_conf = 0.0

        for name, res in named_results.items():
            w = self._weights.get(name, self._default_weight)
            w_score += res["score"] * w
            w_conf += res["confidence"] * w
            total_w += w

        score = w_score / total_w
        confidence = w_conf / total_w

        # ----------------------------------------------------------------
        # Collect all flags from analyzers with weight annotations
        # ----------------------------------------------------------------
        all_flags: list[str] = []
        for name, res in named_results.items():
            w = self._weights.get(name, self._default_weight)
            for flag in res.get("flags", []):
                all_flags.append(f"[{name}|w={w:.2f}] {flag}")

        # ----------------------------------------------------------------
        # Build explanation narrative
        # ----------------------------------------------------------------
        if all_flags:
            explanation = (
                f"Frequency analysis detected {len(all_flags)} suspicious signal(s): "
                + "; ".join(all_flags) + "."
            )
        else:
            explanation = (
                "Frequency analysis found no significant spectral anomalies. "
                "FFT grid patterns, power law statistics, and JPEG compression "
                "fingerprints are consistent with authentic photographic content."
            )

        # ----------------------------------------------------------------
        # Merge feature dicts from all analyzers
        # ----------------------------------------------------------------
        merged_features = {
            "grid": grid_result.get("features", {}),
            "power_law": power_result.get("features", {}),
            "compression": comp_result.get("features", {}),
        }

        return {
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "explanation": explanation,
            "features": merged_features,
        }
