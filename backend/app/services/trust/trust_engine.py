"""
trust_engine.py — Layer 3 Trust & Decision Engine orchestrator.

Responsibilities
----------------
  1. Accept Layer 1 (VerificationResult) and Layer 2 (AIEvidenceResult) evidence.
  2. Build typed ProvenanceEvidence and ForensicsEvidence summaries.
  3. Delegate to DecisionEngine for verdict derivation.
  4. Return a TrustAssessment.

Design
------
  - TrustEngine has no knowledge of HOW evidence was collected.
  - It depends only on typed input models, not on service implementations.
  - New evidence sources can be added by extending the model types without
    modifying the DecisionEngine rules.
  - The engine is stateless per-call and safe for concurrent use.

Dependency Injection:
  - DecisionEngine is injected at construction time.
  - Swap in a custom DecisionEngine subclass for testing or alternative strategies.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.services.trust.models import (
    ProvenanceEvidence,
    ForensicsEvidence,
    TrustAssessment,
)
from app.services.trust.decision_rules import DecisionEngine
from app.services.ai_forensics.models import AIEvidenceResult
from app.services.verification.verification_service import VerificationResult

logger = logging.getLogger(__name__)


class TrustEngine:
    """
    Orchestrates Layer 3 evidence fusion and verdict derivation.

    Accepts structured evidence from both upstream layers, builds typed
    evidence summaries, and delegates to the DecisionEngine for the
    final verdict.

    Usage::

        engine = TrustEngine()

        # With full verification
        assessment = engine.assess(
            ai_evidence=forensics_result,
            verification_result=verification_result,
        )

        # Forensics-only (no provenance watermark found)
        assessment = engine.assess(
            ai_evidence=forensics_result,
            verification_result=None,
            mir_recovered=False,
        )

        # MIR found but image not registered in DB
        assessment = engine.assess(
            ai_evidence=forensics_result,
            verification_result=None,
            mir_recovered=True,
        )
    """

    def __init__(self, decision_engine: DecisionEngine | None = None) -> None:
        """
        Initialize TrustEngine.

        Args:
            decision_engine: Injected DecisionEngine instance.
                             If None, the default DecisionEngine is used.
        """
        self._decision = decision_engine or DecisionEngine()

    def assess(
        self,
        ai_evidence: AIEvidenceResult,
        verification_result: Optional[VerificationResult] = None,
        mir_recovered: bool = False,
    ) -> TrustAssessment:
        """
        Produce a TrustAssessment from Layer 1 and Layer 2 evidence.

        Args:
            ai_evidence:         AIEvidenceResult from DetectionEngine.run().
                                 Always required — AI forensics always runs.
            verification_result: VerificationResult from verify_provenance().
                                 None if provenance extraction or verification failed.
            mir_recovered:       True if a MIR was extracted from the image but
                                 full verification could not complete (e.g., image
                                 not registered in the DB, or pHash missing).
                                 Used by the decision engine to differentiate between
                                 "no watermark" and "watermark present but unverifiable".

        Returns:
            TrustAssessment with verdict, trust score, confidence, and full reasoning.
        """
        prov_evidence = self._build_provenance_evidence(
            verification_result, mir_recovered
        )
        fore_evidence = self._build_forensics_evidence(ai_evidence)

        logger.debug(
            "[TrustEngine] Assessing — "
            "prov.available=%s, prov.verdict=%s, prov.integrity=%s | "
            "fore.ai_prob=%.3f, fore.verdict=%s, fore.detectors=%d",
            prov_evidence.available,
            prov_evidence.provenance_verdict,
            prov_evidence.integrity_score,
            fore_evidence.ai_probability,
            fore_evidence.forensics_verdict,
            fore_evidence.detector_count,
        )

        assessment = self._decision.assess(prov_evidence, fore_evidence)

        logger.info(
            "[TrustEngine] Verdict=%s, Score=%d, Confidence=%.3f",
            assessment.verdict,
            assessment.trust_score,
            assessment.confidence,
        )

        return assessment

    # ------------------------------------------------------------------
    # Evidence builders (static — pure functions)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_provenance_evidence(
        result: Optional[VerificationResult],
        mir_recovered: bool,
    ) -> ProvenanceEvidence:
        """
        Build a ProvenanceEvidence summary from a VerificationResult.

        If result is None (verification failed or was not attempted):
          - available=False, provenance_verdict=None (no watermark)
          - available=False, provenance_verdict="UNVERIFIED" (MIR found but unverified)

        Args:
            result:        VerificationResult from verify_provenance(), or None.
            mir_recovered: True if a MIR was extracted but verification failed.

        Returns:
            ProvenanceEvidence summary for the DecisionEngine.
        """
        if result is None:
            return ProvenanceEvidence(
                available=False,
                mir_recovered=mir_recovered,
                # If a MIR was recovered but verification failed, signal UNVERIFIED.
                # If no MIR was found at all, signal None (complete absence).
                provenance_verdict="UNVERIFIED" if mir_recovered else None,
                integrity_score=None,
                similarity=None,
                hamming_distance=None,
                recovered_regions=None,
                total_regions=None,
                inconsistent=False,
                pixel_hash_match=None,
                media_id=None,
                dhash_similarity=None,
                local_similarity=None,
                changed_area_percentage=None,
                tamper_type=None,
                severity=None,
            )

        # Full verification result is available
        return ProvenanceEvidence(
            # "available" means we have a verified match in the DB
            available=(result.status == "verified"),
            mir_recovered=True,
            provenance_verdict=result.verification,   # AUTHENTIC | MODIFIED | UNVERIFIED
            integrity_score=result.integrity_score,
            similarity=result.similarity,
            hamming_distance=result.hamming_distance,
            recovered_regions=result.recovered_regions,
            total_regions=result.total_regions,
            # VerificationResult does not expose `inconsistent` field.
            # It is captured internally in the extraction result but not surfaced
            # through the verification schema. Default to False (conservative).
            inconsistent=False,
            pixel_hash_match=result.pixel_hash_match,
            media_id=result.media_id,
            dhash_similarity=result.dhash_similarity,
            local_similarity=result.local_similarity,
            changed_area_percentage=result.changed_area_percentage,
            tamper_type=result.tamper_type,
            severity=result.severity,
        )

    @staticmethod
    def _build_forensics_evidence(evidence: AIEvidenceResult) -> ForensicsEvidence:
        """
        Build a ForensicsEvidence summary from an AIEvidenceResult.

        Args:
            evidence: AIEvidenceResult from DetectionEngine.run().

        Returns:
            ForensicsEvidence summary for the DecisionEngine.
        """
        detector_scores: dict[str, float] = {
            r.engine: r.score
            for r in evidence.detector_breakdown
        }
        return ForensicsEvidence(
            ai_probability=evidence.ai_probability,
            confidence=evidence.confidence,
            forensics_verdict=evidence.verdict,
            detector_count=len(evidence.detector_breakdown),
            explanation=evidence.explanation,
            detector_scores=detector_scores,
        )
