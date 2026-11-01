"""
models.py — Shared, strongly-typed data models for the AI Forensics Engine.

All detector plugins must return a DetectionResult.
The DetectionEngine aggregates them into an AIEvidenceResult.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DetectionResult:
    """
    The canonical output of a single detector plugin.

    Fields
    ------
    engine      : Unique identifier of the detector (e.g. "foundation_clip")
    score       : AI probability estimate in [0.0, 1.0]
    confidence  : Model's self-reported confidence in [0.0, 1.0]
    reason      : Human-readable explanation of what drove the score
    metadata    : Optional dict for extra detector-specific diagnostics
    """
    engine: str
    score: float        # 0.0 = authentic, 1.0 = AI-generated
    confidence: float   # how certain the detector is
    reason: str
    metadata: dict = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"score must be in [0, 1], got {self.score}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


@dataclass(frozen=True)
class AIEvidenceResult:
    """
    The aggregated output of the full AI Forensics Engine.

    Produced by DetectionFusion after collecting all DetectionResults.
    This is the contract consumed by the global Evidence Fusion Engine (Layer 3).

    Fields
    ------
    ai_probability  : Weighted ensemble score in [0.0, 1.0]
    confidence      : Average weighted confidence in [0.0, 1.0]
    verdict         : Human-readable label (AUTHENTIC / AMBIGUOUS / AI_GENERATED)
    explanation     : Narrative summary of the evidence
    detector_breakdown : List of individual DetectionResults contributing to the score
    """
    ai_probability: float
    confidence: float
    verdict: str
    explanation: str
    detector_breakdown: list[DetectionResult] = field(
        default_factory=list, compare=False, hash=False
    )

    # Verdict thresholds (class-level constants — not per-instance)
    THRESHOLD_AUTHENTIC:  float = 0.40
    THRESHOLD_AMBIGUOUS:  float = 0.70

    @classmethod
    def verdict_label(cls, probability: float) -> str:
        """Derive a human-readable verdict from a probability score."""
        if probability < cls.THRESHOLD_AUTHENTIC:
            return "AUTHENTIC"
        if probability < cls.THRESHOLD_AMBIGUOUS:
            return "AMBIGUOUS"
        return "AI_GENERATED"
