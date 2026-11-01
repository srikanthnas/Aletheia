"""
base_detector.py — Abstract base class for all AI Forensics detector plugins.

Every plugin must:
  1. Inherit from AIForensicDetector.
  2. Implement the `analyze` method.
  3. Return a DetectionResult.

This contract ensures that:
  - New detectors can be added without touching the engine.
  - Detector failures are isolated and do not crash the engine.
  - Fusion logic operates on a uniform interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image

from app.services.ai_forensics.models import DetectionResult


class AIForensicDetector(ABC):
    """
    Abstract plugin interface for all AI image forensic detectors.

    Subclasses implement a single `analyze` method that accepts a PIL Image
    and returns a strongly-typed DetectionResult.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique machine-readable identifier for this detector.
        Used as the `engine` field in DetectionResult and in fusion weight lookups.
        Example: "foundation_clip", "statistical_features"
        """
        ...

    @abstractmethod
    def analyze(self, image: Image.Image) -> DetectionResult:
        """
        Run forensic analysis on the provided image.

        Args:
            image: A PIL.Image.Image object (RGB mode).

        Returns:
            DetectionResult — score, confidence, and explanation.

        Raises:
            Any exception is caught and handled by DetectionEngine.
            Detectors should NOT suppress their own exceptions; let the engine handle them.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
