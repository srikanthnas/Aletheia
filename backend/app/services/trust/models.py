"""
models.py — Strongly-typed data models for the Trust & Decision Engine (Layer 3).

Architecture
------------
Layer 3 receives structured evidence from both upstream layers and produces
a single TrustAssessment — the canonical output of the full Aletheia pipeline.

Data Flow:
    Layer 1 (VerificationResult)   ──┐
                                     ├──► TrustEngine ──► TrustAssessment
    Layer 2 (AIEvidenceResult)     ──┘

Design Principles:
  - All models are frozen dataclasses (immutable after construction).
  - No business logic lives here — only data contracts.
  - ProvenanceEvidence and ForensicsEvidence isolate layer concerns.
  - TrustAssessment is the only type that crosses the API boundary (via schemas).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Layer 1 Evidence Summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProvenanceEvidence:
    """
    Structured summary of Layer 1 (Provenance Engine) evidence.

    Built by TrustEngine from a VerificationResult or from partial extraction
    data when full verification was not possible (e.g., unregistered image).

    Fields
    ------
    available         : True if the provenance data was successfully verified
                        against a registered DB record.
    mir_recovered     : True if a valid MIR was extracted from the image,
                        regardless of whether verification against the DB succeeded.
    provenance_verdict: AUTHENTIC | MODIFIED | UNVERIFIED | None (if no MIR).
    integrity_score   : 0–100 integrity score from IntegrityAssessment.
                        None if verification was not performed.
    similarity        : pHash similarity % [0–100]. None if unavailable.
    hamming_distance  : pHash Hamming distance [0–64]. None if unavailable.
    recovered_regions : Number of ADPE regions where MIR was successfully read.
    total_regions     : Total number of ADPE regions in the image grid.
    inconsistent      : True if different MIRs were found across regions.
    media_id          : Recovered media_id from the MIR. None if extraction failed.
    """

    available: bool
    mir_recovered: bool
    provenance_verdict: str | None
    integrity_score: int | None
    similarity: float | None
    hamming_distance: int | None
    recovered_regions: int | None
    total_regions: int | None
    inconsistent: bool
    pixel_hash_match: bool | None = None
    media_id: str | None = None
    dhash_similarity: float | None = None
    local_similarity: float | None = None
    changed_area_percentage: float | None = None
    tamper_type: str | None = None
    severity: str | None = None


# ---------------------------------------------------------------------------
# Layer 2 Evidence Summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ForensicsEvidence:
    """
    Structured summary of Layer 2 (AI Forensics Engine) evidence.

    Built directly from an AIEvidenceResult. All fields have corresponding
    sources in the forensics engine output, ensuring zero information loss.

    Fields
    ------
    ai_probability   : Weighted ensemble AI probability in [0.0, 1.0].
                       0.0 = very likely authentic. 1.0 = very likely AI-generated.
    confidence       : Average weighted confidence across all detectors [0.0, 1.0].
    forensics_verdict: AUTHENTIC | AMBIGUOUS | AI_GENERATED.
    detector_count   : Number of detector plugins that returned results.
    explanation      : Narrative summary from the DetectionFusion layer.
    detector_scores  : Per-detector score keyed by engine name.
    """

    ai_probability: float
    confidence: float
    forensics_verdict: str
    detector_count: int
    explanation: str
    detector_scores: dict[str, float] = field(
        default_factory=dict, compare=False, hash=False
    )


# ---------------------------------------------------------------------------
# Layer 3 Trust Assessment — canonical pipeline output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrustAssessment:
    """
    The final, unified output of the Aletheia Trust & Decision Engine (Layer 3).

    Combines Layer 1 (Provenance) and Layer 2 (AI Forensics) evidence through
    a transparent, rule-based decision process (see decision_rules.py).

    Verdicts
    --------
    AUTHENTIC    : Image is genuine. Provenance is intact and forensics agree.
    AI_GENERATED : Image is AI-generated. Confirmed by forensics ± provenance.
    MODIFIED     : Original provenance found, but image has been visually altered.
    TAMPERED     : Provenance found but its integrity has been compromised —
                   pHash mismatch, region inconsistency, or Hamming anomaly.
    SUSPICIOUS   : Provenance claims authenticity but AI forensics strongly
                   disagrees. Possible provenance spoofing or AI replacement.
    UNVERIFIED   : Insufficient or conflicting evidence to make a determination.

    Fields
    ------
    trust_score        : Overall trust score [0, 100]. Higher = more trustworthy.
    verdict            : Final verdict string (see Verdicts above).
    confidence         : Engine confidence in the verdict [0.0, 1.0].
    reasoning          : Full human-readable reasoning narrative.
    provenance_available: True if active provenance was successfully verified.
    provenance_verdict : Provenance layer verdict. None if no MIR found.
    forensics_verdict  : AI Forensics layer verdict.
    ai_probability     : Raw AI probability from the forensics engine.
    integrity_score    : Provenance integrity score [0, 100]. None if unavailable.
    evidence_summary   : Ordered list of key evidence bullets.
    provenance_evidence: Full ProvenanceEvidence record (for detailed responses).
    forensics_evidence : Full ForensicsEvidence record (for detailed responses).
    """

    trust_score: int
    verdict: str
    confidence: float
    reasoning: str
    provenance_available: bool
    provenance_verdict: str | None
    forensics_verdict: str
    ai_probability: float
    integrity_score: int | None
    evidence_summary: list[str] = field(
        default_factory=list, compare=False, hash=False
    )
    provenance_evidence: ProvenanceEvidence | None = field(
        default=None, compare=False, hash=False
    )
    forensics_evidence: ForensicsEvidence | None = field(
        default=None, compare=False, hash=False
    )

    # Valid verdict set (class-level constant)
    VALID_VERDICTS: frozenset[str] = frozenset({
        "AUTHENTIC", "AI_GENERATED", "MODIFIED",
        "TAMPERED", "SUSPICIOUS", "UNVERIFIED",
    })

    def __post_init__(self) -> None:
        if self.verdict not in self.VALID_VERDICTS:
            raise ValueError(
                f"Invalid verdict '{self.verdict}'. "
                f"Must be one of: {sorted(self.VALID_VERDICTS)}"
            )
        if not (0 <= self.trust_score <= 100):
            raise ValueError(
                f"trust_score must be in [0, 100], got {self.trust_score}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )
        if not (0.0 <= self.ai_probability <= 1.0):
            raise ValueError(
                f"ai_probability must be in [0.0, 1.0], got {self.ai_probability}"
            )
