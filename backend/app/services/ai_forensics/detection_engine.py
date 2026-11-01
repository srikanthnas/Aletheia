"""
detection_engine.py — Orchestration engine for the AI Forensics plugin system.

The DetectionEngine:
  1. Holds a registry of AIForensicDetector plugins.
  2. Executes all registered detectors independently in sequence.
  3. Collects their DetectionResults, gracefully handling individual failures.
  4. Passes the collected results to DetectionFusion for aggregation.
  5. Returns a single AIEvidenceResult.

Architecture Notes
------------------
- Detectors are registered via dependency injection (no internal imports).
- Plugin failures are isolated — one failing detector never terminates the engine.
- The engine is stateless per-call; it can be reused across requests.
- New detectors are added by:
      engine.register(MyNewDetector())
  No other code changes are needed.
"""
from __future__ import annotations

import logging
from typing import Sequence

from PIL import Image

from app.services.ai_forensics.base_detector import AIForensicDetector
from app.services.ai_forensics.fusion import DEFAULT_WEIGHTS, DetectionFusion
from app.services.ai_forensics.models import AIEvidenceResult, DetectionResult

logger = logging.getLogger(__name__)


class DetectionEngine:
    """
    Orchestrates an ensemble of AIForensicDetector plugins.

    Usage::

        engine = DetectionEngine.default()
        result = engine.run(image)
        print(result.verdict, result.ai_probability)
    """

    def __init__(
        self,
        detectors: Sequence[AIForensicDetector] | None = None,
        fusion: DetectionFusion | None = None,
    ) -> None:
        self._detectors: list[AIForensicDetector] = list(detectors or [])
        self._fusion = fusion or DetectionFusion(weights=DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # Plugin registry
    # ------------------------------------------------------------------

    def register(self, detector: AIForensicDetector) -> "DetectionEngine":
        """
        Register a detector plugin.
        Returns self to allow fluent chaining:
            engine.register(A()).register(B())
        """
        if not isinstance(detector, AIForensicDetector):
            raise TypeError(
                f"Expected AIForensicDetector, got {type(detector).__name__}"
            )
        self._detectors.append(detector)
        logger.debug("[DetectionEngine] Registered detector: %s", detector.name)
        return self

    def detectors(self) -> list[AIForensicDetector]:
        """Return a read-only copy of the registered detector list."""
        return list(self._detectors)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def run(self, image: Image.Image) -> AIEvidenceResult:
        """
        Execute all registered detectors and return a fused AIEvidenceResult.

        Individual detector failures are caught, logged, and skipped.
        The engine continues with the remaining detectors.

        Args:
            image: PIL Image to analyze.

        Returns:
            AIEvidenceResult with aggregated probability and breakdown.
        """
        if not self._detectors:
            logger.warning("[DetectionEngine] No detectors registered — returning empty result.")
            return self._fusion.fuse([])

        image_rgb = image.convert("RGB")
        collected: list[DetectionResult] = []

        for detector in self._detectors:
            try:
                logger.debug("[DetectionEngine] Running detector: %s", detector.name)
                result = detector.analyze(image_rgb)
                collected.append(result)
                logger.debug(
                    "[DetectionEngine] %s → score=%.3f confidence=%.3f",
                    detector.name, result.score, result.confidence,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[DetectionEngine] Detector '%s' failed: %s — skipping.",
                    detector.name, exc, exc_info=True,
                )

        return self._fusion.fuse(collected)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "DetectionEngine":
        """
        Construct the default DetectionEngine with the recommended plugin set.

        Import of concrete detectors happens here (lazy) so that the engine
        module itself stays import-free of heavy ML libraries.
        """
        from app.services.ai_forensics.detectors.foundation_detector import FoundationDetector
        from app.services.ai_forensics.detectors.statistical_detector import StatisticalDetector
        from app.services.ai_forensics.detectors.artifact_detector import ArtifactDetector
        from app.services.ai_forensics.detectors.frequency_detector import FrequencyDetector

        engine = cls(fusion=DetectionFusion(weights=DEFAULT_WEIGHTS))
        engine.register(FoundationDetector())
        engine.register(StatisticalDetector())
        engine.register(ArtifactDetector())
        engine.register(FrequencyDetector())
        return engine
