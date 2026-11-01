"""
schemas/trust.py — API I/O contracts for the Trust & Decision Engine (Layer 3).

These Pydantic models define the exact shape of POST /api/assess responses.
They are decoupled from the internal service models (TrustAssessment, etc.)
following the clean architecture principle of separate data contracts per layer.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested schemas (evidence sub-documents)
# ---------------------------------------------------------------------------

class ProvenanceEvidenceSchema(BaseModel):
    """Layer 1 evidence summary included in the TrustResponse."""

    available: bool = Field(
        ...,
        description="True if provenance was verified against a registered DB record.",
    )
    mir_recovered: bool = Field(
        ...,
        description="True if a MIR was extracted from the image, regardless of DB status.",
    )
    provenance_verdict: Optional[str] = Field(
        None,
        description="AUTHENTIC | MODIFIED | UNVERIFIED | null",
        examples=["AUTHENTIC"],
    )
    integrity_score: Optional[int] = Field(
        None,
        description="Integrity score [0–100]. Null if verification not performed.",
        examples=[97],
    )
    similarity: Optional[float] = Field(
        None,
        description="pHash similarity % [0–100]. Null if unavailable.",
        examples=[100.0],
    )
    hamming_distance: Optional[int] = Field(
        None,
        description="pHash Hamming distance [0–64]. Null if unavailable.",
        examples=[0],
    )
    recovered_regions: Optional[int] = Field(
        None,
        description="Number of ADPE regions where MIR was recovered.",
        examples=[4],
    )
    total_regions: Optional[int] = Field(
        None,
        description="Total ADPE regions in the image grid.",
        examples=[4],
    )
    inconsistent: bool = Field(
        ...,
        description="True if different MIRs were found across regions.",
    )
    pixel_hash_match: Optional[bool] = Field(
        None,
        description="True when decoded pixels exactly match the registered embedded baseline.",
    )
    media_id: Optional[str] = Field(None, description="Recovered media UUID from the MIR.")
    dhash_similarity: Optional[float] = Field(None, description="dHash similarity [0–100].")
    local_similarity: Optional[float] = Field(None, description="Mean local structural similarity [0–100].")
    changed_area_percentage: Optional[float] = Field(None, description="Estimated changed comparison-region percentage.")
    tamper_type: Optional[str] = Field(None, description="Tamper/modification category.")
    severity: Optional[str] = Field(None, description="LOW | MEDIUM | HIGH")


class ForensicsEvidenceSchema(BaseModel):
    """Layer 2 evidence summary included in the TrustResponse."""

    ai_probability: float = Field(
        ...,
        description="Weighted ensemble AI probability [0.0–1.0].",
        examples=[0.12],
    )
    confidence: float = Field(
        ...,
        description="Average weighted detector confidence [0.0–1.0].",
        examples=[0.87],
    )
    forensics_verdict: str = Field(
        ...,
        description="AUTHENTIC | AMBIGUOUS | AI_GENERATED",
        examples=["AUTHENTIC"],
    )
    detector_count: int = Field(
        ...,
        description="Number of detector plugins that returned results.",
        examples=[4],
    )
    explanation: str = Field(
        ...,
        description="Narrative summary from the DetectionFusion layer.",
    )
    detector_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-detector AI scores keyed by engine name.",
        examples=[{"foundation_clip": 0.08, "statistical_features": 0.25}],
    )


class DetectorBreakdownItem(BaseModel):
    """Per-detector result included in the TrustResponse breakdown."""

    engine: str = Field(..., examples=["foundation_clip"])
    score: float = Field(..., description="AI probability from this detector.", examples=[0.08])
    confidence: float = Field(..., examples=[0.85])
    reason: str = Field(..., description="Human-readable explanation from this detector.")
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class TrustResponse(BaseModel):
    """
    Response from POST /api/assess — unified Aletheia Trust Assessment.

    Contains the final verdict, trust score, full reasoning, and complete
    evidence breakdown from all three layers.
    """

    # ── Primary verdict ──────────────────────────────────────────────
    trust_score: int = Field(
        ...,
        description="Overall trust score [0–100]. Higher = more trustworthy.",
        examples=[94],
    )
    verdict: str = Field(
        ...,
        description=(
            "Final verdict: AUTHENTIC | AI_GENERATED | MODIFIED | "
            "TAMPERED | SUSPICIOUS | UNVERIFIED"
        ),
        examples=["AUTHENTIC"],
    )
    confidence: float = Field(
        ...,
        description="Engine confidence in the verdict [0.0–1.0].",
        examples=[0.92],
    )
    reasoning: str = Field(
        ...,
        description="Full human-readable reasoning narrative from the Decision Engine.",
    )

    # ── Layer summaries ───────────────────────────────────────────────
    provenance_available: bool = Field(
        ...,
        description="True if active provenance was successfully verified.",
    )
    provenance_verdict: Optional[str] = Field(
        None,
        description="Provenance layer verdict. Null if no MIR was found.",
        examples=["AUTHENTIC"],
    )
    forensics_verdict: str = Field(
        ...,
        description="AI Forensics layer verdict: AUTHENTIC | AMBIGUOUS | AI_GENERATED",
        examples=["AUTHENTIC"],
    )
    ai_probability: float = Field(
        ...,
        description="Raw weighted ensemble AI probability from the forensics engine.",
        examples=[0.12],
    )
    integrity_score: Optional[int] = Field(
        None,
        description="Provenance integrity score [0–100]. Null if unavailable.",
        examples=[97],
    )

    # ── Evidence detail ───────────────────────────────────────────────
    evidence_summary: list[str] = Field(
        default_factory=list,
        description="Ordered list of key evidence bullets used to derive the verdict.",
    )
    provenance_evidence: Optional[ProvenanceEvidenceSchema] = Field(
        None,
        description="Full Layer 1 evidence breakdown.",
    )
    forensics_evidence: Optional[ForensicsEvidenceSchema] = Field(
        None,
        description="Full Layer 2 evidence breakdown.",
    )
    detector_breakdown: list[DetectorBreakdownItem] = Field(
        default_factory=list,
        description="Per-detector results from the AI Forensics Engine.",
    )
