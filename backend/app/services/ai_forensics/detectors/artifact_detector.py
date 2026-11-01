"""
detectors/artifact_detector.py — Classical computer-vision artifact detector plugin.

Extends AIForensicDetector and integrates cleanly into the DetectionEngine
without any changes to existing detectors, the engine, or the fusion layer.

Architecture
------------
ArtifactDetector
  ├── TextureAnalyzer  (LBP, texture entropy, local variance CoV)
  ├── EdgeAnalyzer     (Canny density, Laplacian variance, continuity, strength std)
  └── ArtifactFusion   (configurable weighted combination)
        ↓
  DetectionResult(engine="artifact_cv", score, confidence, reason, metadata)

The detector is fully self-contained:
  * Register: engine.register(ArtifactDetector())
  * Remove:   simply don't register it — zero other changes needed.
"""
from __future__ import annotations

from PIL import Image

from app.services.ai_forensics.base_detector import AIForensicDetector
from app.services.ai_forensics.models import DetectionResult
from app.services.ai_forensics.artifact.texture import TextureAnalyzer
from app.services.ai_forensics.artifact.edges import EdgeAnalyzer
from app.services.ai_forensics.artifact.fusion import ArtifactFusion


class ArtifactDetector(AIForensicDetector):
    """
    Plugin that detects AI-generation artifacts using classical computer vision.

    Combines texture (LBP-based) and edge (Canny/Laplacian-based) analysis
    through an internal weighted fusion, returning a single DetectionResult
    consistent with the AIForensicDetector interface.

    The internal fusion weights are configurable via the constructor:

        ArtifactDetector(weights={"texture": 0.60, "edges": 0.40})
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._texture = TextureAnalyzer()
        self._edges   = EdgeAnalyzer()
        self._fusion  = ArtifactFusion(weights=weights)

    @property
    def name(self) -> str:
        return "artifact_cv"

    def analyze(self, image: Image.Image) -> DetectionResult:
        """
        Run texture and edge analysis, fuse the results, and return a DetectionResult.

        Args:
            image: PIL Image (any mode — converted to RGB internally).

        Returns:
            DetectionResult with score, confidence, reason, and feature metadata.
        """
        image_rgb = image.convert("RGB")

        # ----------------------------------------------------------------
        # 1. Run sub-analyzers
        # ----------------------------------------------------------------
        texture_result = self._texture.analyze(image_rgb)
        edge_result    = self._edges.analyze(image_rgb)

        # ----------------------------------------------------------------
        # 2. Fuse
        # ----------------------------------------------------------------
        fused = self._fusion.combine(texture_result, edge_result)

        # ----------------------------------------------------------------
        # 3. Wrap into DetectionResult
        # ----------------------------------------------------------------
        return DetectionResult(
            engine=self.name,
            score=fused["score"],
            confidence=fused["confidence"],
            reason=fused["explanation"],
            metadata={
                "texture": texture_result["features"],
                "edges":   edge_result["features"],
            },
        )
