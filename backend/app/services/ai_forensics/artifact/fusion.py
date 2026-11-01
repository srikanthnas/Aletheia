"""
artifact/fusion.py — Combines Texture and Edge analyzer scores.

Design
------
* Weights are injected — not hardcoded in the analyzers.
* Unknown analyzer names receive the default weight.
* Produces a unified (score, confidence, explanation) triple consumed by
  ArtifactDetector → DetectionResult.
"""
from __future__ import annotations

# Default weights: texture and edges are treated as equally informative.
# These can be overridden by passing a custom weights dict to ArtifactFusion().
DEFAULT_WEIGHTS: dict[str, float] = {
    "texture": 0.50,
    "edges":   0.50,
}
DEFAULT_WEIGHT = 0.40


class ArtifactFusion:
    """
    Weighted-average combiner for artifact sub-analyzer outputs.

    Each analyzer returns a dict: {score, confidence, flags, features}.
    ArtifactFusion produces a single (score, confidence, explanation) triple.

    Usage::

        fusion = ArtifactFusion()
        result = fusion.combine(texture_result, edge_result)
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        default_weight: float = DEFAULT_WEIGHT,
    ) -> None:
        self._weights = weights if weights is not None else DEFAULT_WEIGHTS
        self._default_weight = default_weight

    def combine(
        self,
        texture_result: dict,
        edge_result: dict,
    ) -> dict[str, object]:
        """
        Combine texture and edge analyzer results.

        Args:
            texture_result : output dict from TextureAnalyzer.analyze()
            edge_result    : output dict from EdgeAnalyzer.analyze()

        Returns:
            dict with keys: score, confidence, explanation, features
        """
        named_results = {
            "texture": texture_result,
            "edges":   edge_result,
        }

        total_w = 0.0
        w_score = 0.0
        w_conf  = 0.0

        for name, res in named_results.items():
            w = self._weights.get(name, self._default_weight)
            w_score += res["score"]      * w
            w_conf  += res["confidence"] * w
            total_w += w

        score      = w_score / total_w
        confidence = w_conf  / total_w

        # ----------------------------------------------------------------
        # Collect all flags from both analyzers for the explanation
        # ----------------------------------------------------------------
        all_flags: list[str] = []
        for name, res in named_results.items():
            w = self._weights.get(name, self._default_weight)
            for flag in res.get("flags", []):
                all_flags.append(f"[{name}|w={w:.2f}] {flag}")

        if all_flags:
            explanation = (
                f"Artifact analysis detected {len(all_flags)} suspicious signal(s): "
                + "; ".join(all_flags) + "."
            )
        else:
            explanation = (
                "Artifact analysis found no significant texture or edge anomalies. "
                "Visual signals are consistent with natural photographic content."
            )

        # Merge feature dicts from both analyzers for downstream diagnostics
        merged_features = {
            "texture": texture_result.get("features", {}),
            "edges":   edge_result.get("features",   {}),
        }

        return {
            "score":       round(score, 4),
            "confidence":  round(confidence, 4),
            "explanation": explanation,
            "features":    merged_features,
        }
