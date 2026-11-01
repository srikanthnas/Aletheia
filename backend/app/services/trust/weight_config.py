"""
weight_config.py — Centralized, runtime-updatable detector fusion weight registry.

Architecture
------------
This module is the single source of truth for all detector weights used by
DetectionFusion in the AI Forensics Engine.

Before this module existed, weights were hardcoded as a literal dict in fusion.py.
This had two problems:
  1. The `frequency_spectral` detector was missing from DEFAULT_WEIGHTS,
     silently falling through to the DEFAULT_WEIGHT fallback.
  2. No path for updating weights after benchmarking without touching
     detector or engine code.

This module solves both problems:
  - All four detector weights are explicitly declared.
  - Weights can be updated at runtime via update_weights() without restarting.
  - The calibration interface accepts a BenchmarkReport and derives new weights.

Design Principle
----------------
The DetectionFusion remains completely unchanged. It just imports
DETECTOR_WEIGHTS from here instead of defining a local constant.
This is the minimum-change approach that adds calibration capability.

Weight Derivation Philosophy
-----------------------------
Default weights are assigned based on the following research reasoning:

  foundation_clip (0.50):
    CLIP zero-shot embedding provides the best cross-model generalization
    (UnivFD, CVPR 2024). Given highest weight.

  frequency_spectral (0.20):
    Provides orthogonal evidence via FFT/DCT analysis. Strong for GANs,
    weaker for modern diffusion models. Moderate weight.

  statistical_features (0.15):
    Fast, lightweight, interpretable baseline. Useful for trivial cases
    but less discriminative for high-quality AI images.

  artifact_cv (0.15):
    Classical CV (LBP + Canny). Complements statistical but overlaps partially.
    Lower weight to avoid double-counting related signals.

After running benchmarks with a labeled dataset, use calibrate_from_benchmark()
to derive evidence-based weights that replace these defaults.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.report_generator import BenchmarkReport

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical default weights
# All four implemented detectors are explicitly listed.
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS: dict[str, float] = {
    "foundation_clip":      0.50,   # CLIP zero-shot — best cross-model generalization
    "frequency_spectral":   0.20,   # Spectral FFT/DCT — orthogonal frequency evidence
    "statistical_features": 0.15,   # Handcrafted stats — fast, interpretable baseline
    "artifact_cv":          0.15,   # Classical CV — texture + edge analysis
}

# Fallback for any future detector not yet listed above
DEFAULT_FALLBACK_WEIGHT: float = 0.25

# Runtime weight registry (starts as a copy of defaults)
_active_weights: dict[str, float] = dict(_DEFAULT_WEIGHTS)


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def get_weights() -> dict[str, float]:
    """
    Return the currently active detector fusion weights.

    Returns a copy — callers cannot mutate the registry directly.
    This is the function DetectionFusion imports.
    """
    return dict(_active_weights)


def get_fallback_weight() -> float:
    """Return the fallback weight for detectors not in the registry."""
    return DEFAULT_FALLBACK_WEIGHT


def update_weights(new_weights: dict[str, float]) -> None:
    """
    Update the runtime weight registry.

    Updates only the keys provided — unspecified detectors retain
    their current weights. Validates that all values are in [0.0, 1.0].

    Args:
        new_weights: Dict mapping engine name to new weight.

    Raises:
        ValueError: If any weight is outside [0.0, 1.0].

    Example::

        from app.services.trust.weight_config import update_weights
        update_weights({"foundation_clip": 0.60, "frequency_spectral": 0.25})
    """
    global _active_weights
    for name, w in new_weights.items():
        if not (0.0 <= w <= 1.0):
            raise ValueError(
                f"Weight for '{name}' must be in [0.0, 1.0], got {w}"
            )
    _active_weights.update(new_weights)
    logger.info("[WeightConfig] Weights updated: %s", new_weights)


def reset_to_defaults() -> None:
    """Reset the runtime weight registry to the built-in defaults."""
    global _active_weights
    _active_weights = dict(_DEFAULT_WEIGHTS)
    logger.info("[WeightConfig] Weights reset to defaults.")


def calibrate_from_benchmark(report: "BenchmarkReport") -> dict[str, float]:
    """
    Derive calibrated weights from a BenchmarkReport.

    Calibration strategy: normalize F1-scores to sum to 1.0,
    then use each detector's relative F1-score as its weight.

    This gives higher weight to detectors that demonstrated better
    discrimination in the benchmark — a direct evidence-based approach.

    If a detector has F1 = 0 (complete failure), it receives a small
    floor weight (0.05) rather than zero to avoid silencing it entirely.

    Args:
        report: BenchmarkReport from BenchmarkRunner.run().

    Returns:
        Dict of calibrated weights. Does NOT automatically apply them —
        call update_weights(calibrated) to activate.

    Example::

        from app.services.trust.weight_config import calibrate_from_benchmark, update_weights
        calibrated = calibrate_from_benchmark(benchmark_report)
        print(calibrated)
        update_weights(calibrated)  # activate after inspection
    """
    FLOOR_WEIGHT = 0.05  # Minimum weight for any detector

    f1_scores = {m.engine: max(m.f1_score, FLOOR_WEIGHT) for m in report.detector_metrics}

    if not f1_scores:
        logger.warning("[WeightConfig] Empty benchmark report — cannot calibrate.")
        return {}

    total_f1 = sum(f1_scores.values())

    calibrated: dict[str, float] = {
        engine: round(f1 / total_f1, 4)
        for engine, f1 in f1_scores.items()
    }

    logger.info(
        "[WeightConfig] Calibrated weights from benchmark: %s",
        calibrated,
    )
    return calibrated
