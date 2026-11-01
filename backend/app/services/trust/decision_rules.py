"""
decision_rules.py — Transparent, rule-based evidence fusion for the Trust Engine.

Architecture
------------
The DecisionEngine applies a five-stage deterministic rule system to combine
Layer 1 (provenance) and Layer 2 (AI forensics) evidence into a final verdict
and trust score.

Design Philosophy
-----------------
This is deliberately NOT a black-box weighted average. Each decision is driven
by explicit, auditable rules with human-readable justifications. This makes the
reasoning transparent and defensible in a research presentation or audit.

Stage Pipeline
--------------
  Stage 1 — Tampering Gate     : Detect provenance manipulation signals first.
                                  Bypasses all other stages if confirmed.
  Stage 2 — Suspicious Gate    : Detect provenance/forensics conflict.
                                  Provenance intact but forensics signals AI.
  Stage 3 — Primary Routing    : Route to correct verdict based on available evidence.
                                  Path A: No provenance → forensics-only decision.
                                  Path B: Provenance available → cross-layer decision.
  Stage 4 — Trust Score        : Compute 0–100 score from all evidence streams.
  Stage 5 — Narrative Build    : Generate human-readable reasoning chain.

Tunable Parameters
------------------
All thresholds are module-level constants. They can be adjusted without touching
any rule logic. To recalibrate after benchmarking, update only these constants.
"""
from __future__ import annotations

from app.services.trust.models import (
    ProvenanceEvidence,
    ForensicsEvidence,
    TrustAssessment,
)


# ---------------------------------------------------------------------------
# Verdict string constants (avoid magic strings throughout)
# ---------------------------------------------------------------------------

VERDICT_AUTHENTIC    = "AUTHENTIC"
VERDICT_AI_GENERATED = "AI_GENERATED"
VERDICT_MODIFIED     = "MODIFIED"
VERDICT_TAMPERED     = "TAMPERED"
VERDICT_SUSPICIOUS   = "SUSPICIOUS"
VERDICT_UNVERIFIED   = "UNVERIFIED"


# ---------------------------------------------------------------------------
# Decision thresholds (tunable)
# ---------------------------------------------------------------------------

# Forensics — ai_probability classification boundaries
_FORENSICS_AUTHENTIC_MAX = 0.35   # Below this → forensically authentic
_FORENSICS_AI_MIN        = 0.65   # Above this → forensically AI-generated
# Values between the two boundaries → AMBIGUOUS

# Provenance integrity classification boundaries
_INTEGRITY_AUTHENTIC_MIN = 85     # >= this → AUTHENTIC integrity
_INTEGRITY_MODIFIED_MIN  = 60     # >= this → MODIFIED (partial integrity)

# pHash similarity boundaries
_SIMILARITY_AUTHENTIC_MIN = 90.0  # >= this → high visual match
_SIMILARITY_TAMPERED_MAX  = 70.0  # < this  → strong tampering signal

# Hamming distance boundaries
_HAMMING_AUTHENTIC_MAX   = 8      # <= this → close perceptual match
_HAMMING_TAMPERED_MIN    = 30     # >= this → extreme divergence signal

# Confidence adjustments
_CONFIDENCE_AGREEMENT_BONUS   = 0.10   # Both layers agree → add this
_CONFIDENCE_CONFLICT_PENALTY  = 0.15   # Layers conflict   → subtract this
_CONFIDENCE_NO_PROV_PENALTY   = 0.12   # No provenance     → subtract this


class DecisionEngine:
    """
    Applies a multi-stage rule system to produce a TrustAssessment.

    The engine is stateless and reusable across requests. All parameters
    are derived from the ProvenanceEvidence and ForensicsEvidence inputs.

    Usage::

        engine = DecisionEngine()
        assessment = engine.assess(provenance_evidence, forensics_evidence)
    """

    def assess(
        self,
        prov: ProvenanceEvidence,
        fore: ForensicsEvidence,
    ) -> TrustAssessment:
        """
        Apply the full five-stage decision pipeline.

        Args:
            prov: Structured Layer 1 provenance evidence summary.
            fore: Structured Layer 2 forensics evidence summary.

        Returns:
            TrustAssessment with verdict, score, confidence, and full reasoning.
        """
        evidence: list[str] = []

        # ----------------------------------------------------------------
        # Stage 1 — Tampering Gate
        # ----------------------------------------------------------------
        is_tampered, tamper_bullets = self._detect_tampering(prov)
        evidence.extend(tamper_bullets)

        if is_tampered:
            verdict    = VERDICT_TAMPERED
            score      = self._score_tampered(prov)
            confidence = self._compute_confidence(prov, fore, layers_agree=False)
            return self._make_assessment(verdict, score, confidence, evidence, prov, fore)

        # ----------------------------------------------------------------
        # Stage 2 — Suspicious Gate
        # Provenance intact + forensics strongly says AI
        # ----------------------------------------------------------------
        if self._is_suspicious(prov, fore):
            evidence.append(
                f"CONFLICT DETECTED: Provenance verdict '{prov.provenance_verdict}' "
                f"(integrity {prov.integrity_score}/100) contradicts AI Forensics "
                f"AI probability of {fore.ai_probability:.1%}. "
                "Possible provenance spoofing — an AI image may have had authentic "
                "provenance data copied into it."
            )
            verdict    = VERDICT_SUSPICIOUS
            score      = self._score_suspicious(prov, fore)
            confidence = self._compute_confidence(prov, fore, layers_agree=False)
            return self._make_assessment(verdict, score, confidence, evidence, prov, fore)

        # ----------------------------------------------------------------
        # Stage 3 — Primary Routing
        # ----------------------------------------------------------------
        verdict, route_bullets, layers_agree = self._route_verdict(prov, fore)
        evidence.extend(route_bullets)

        # ----------------------------------------------------------------
        # Stage 4 — Trust Score
        # ----------------------------------------------------------------
        score = self._compute_trust_score(prov, fore, verdict)

        # ----------------------------------------------------------------
        # Stage 5 — Confidence
        # ----------------------------------------------------------------
        confidence = self._compute_confidence(prov, fore, layers_agree=layers_agree)

        return self._make_assessment(verdict, score, confidence, evidence, prov, fore)

    # ------------------------------------------------------------------
    # Stage 1: Tampering detection
    # ------------------------------------------------------------------

    def _detect_tampering(
        self, prov: ProvenanceEvidence
    ) -> tuple[bool, list[str]]:
        """
        Detect tampering signals in provenance data.

        Tampering means a valid MIR was recovered but the image content
        has diverged significantly from its registered fingerprint. This
        differs from MODIFIED (minor visual change) in that the divergence
        is large enough to indicate deliberate manipulation.

        Returns:
            (is_tampered, evidence_bullets)
        """
        if not prov.available:
            return False, []

        bullets: list[str] = []
        signals = 0

        # Signal 1: Critically low pHash similarity despite valid MIR
        if prov.similarity is not None and prov.similarity < _SIMILARITY_TAMPERED_MAX:
            signals += 1
            bullets.append(
                f"pHash similarity critically low ({prov.similarity:.1f}% < "
                f"{_SIMILARITY_TAMPERED_MAX}% threshold) — image content has "
                "diverged far beyond perceptual noise tolerance."
            )

        # Signal 2: Extreme Hamming distance
        if (
            prov.hamming_distance is not None
            and prov.hamming_distance >= _HAMMING_TAMPERED_MIN
        ):
            signals += 1
            bullets.append(
                f"Hamming distance anomaly ({prov.hamming_distance}/64 bits ≥ "
                f"{_HAMMING_TAMPERED_MIN} threshold) — perceptual hash mismatch "
                "is far beyond natural image noise."
            )

        # Signal 3: Exact pixel mismatch + localized structural mismatch.
        # A pixel mismatch alone is not enough: JPEG/resize/brightness can change
        # pixels while preserving the underlying content. A local similarity drop
        # is the stronger evidence for actual content manipulation.
        if (
            prov.pixel_hash_match is False
            and prov.local_similarity is not None
            and prov.local_similarity < 80.0
        ):
            signals += 1
            area = prov.changed_area_percentage or 0.0
            bullets.append(
                f"Localized integrity mismatch detected ({prov.local_similarity:.1f}% local similarity; "
                f"~{area:.1f}% of regions changed) — consistent with post-registration content editing."
            )

        # Signal 4: Cross-region MIR inconsistency (payload splicing signal)
        if prov.inconsistent:
            signals += 1
            bullets.append(
                "Multi-region MIR inconsistency detected — different provenance "
                "payloads were recovered from different image regions. "
                "This is a strong indicator of selective region replacement or "
                "payload splicing."
            )

        return signals >= 1, bullets

    # ------------------------------------------------------------------
    # Stage 2: Suspicious signal detection
    # ------------------------------------------------------------------

    def _is_suspicious(
        self, prov: ProvenanceEvidence, fore: ForensicsEvidence
    ) -> bool:
        """
        Detect provenance/forensics conflict.

        A 'suspicious' image has:
          - Valid provenance claiming HIGH integrity authenticity, AND
          - AI Forensics producing a strong AI-generated signal.

        This pattern is consistent with:
          1. An AI-generated image that had authentic provenance data spliced in.
          2. An image where the authentic content was replaced with AI content
             but the original provenance watermark survived.
        """
        if not prov.available:
            return False

        provenance_claims_authentic = (
            prov.provenance_verdict == VERDICT_AUTHENTIC
            and prov.integrity_score is not None
            and prov.integrity_score >= _INTEGRITY_AUTHENTIC_MIN
        )
        forensics_says_ai = fore.ai_probability >= _FORENSICS_AI_MIN

        return provenance_claims_authentic and forensics_says_ai

    # ------------------------------------------------------------------
    # Stage 3: Primary routing
    # ------------------------------------------------------------------

    def _route_verdict(
        self,
        prov: ProvenanceEvidence,
        fore: ForensicsEvidence,
    ) -> tuple[str, list[str], bool]:
        """
        Route to the correct verdict based on available evidence.

        Returns:
            (verdict, evidence_bullets, layers_agree)
            layers_agree: True when both layers point to the same conclusion.
        """
        bullets: list[str] = []

        # ── Path A: No provenance ─────────────────────────────────────
        if not prov.available:
            bullets.append(
                "No Aletheia provenance watermark found in this image. "
                "Verdict is derived exclusively from AI Forensics evidence."
                + (" (Note: a MIR was extracted but could not be verified "
                   "against a registered record.)" if prov.mir_recovered else "")
            )

            if fore.ai_probability >= _FORENSICS_AI_MIN:
                bullets.append(
                    f"AI Forensics: HIGH AI probability ({fore.ai_probability:.1%}) "
                    f"from {fore.detector_count} independent detector(s). "
                    f"Forensics verdict: {fore.forensics_verdict}."
                )
                return VERDICT_AI_GENERATED, bullets, True

            if fore.ai_probability <= _FORENSICS_AUTHENTIC_MAX:
                bullets.append(
                    f"AI Forensics: LOW AI probability ({fore.ai_probability:.1%}) — "
                    "image characteristics are consistent with natural photography. "
                    f"Forensics verdict: {fore.forensics_verdict}."
                )
                # Without provenance confirmation, authentic verdict has lower confidence
                return VERDICT_AUTHENTIC, bullets, True

            # Ambiguous forensics with no provenance
            bullets.append(
                f"AI Forensics: AMBIGUOUS signal ({fore.ai_probability:.1%}) — "
                f"between {_FORENSICS_AUTHENTIC_MAX:.0%} and {_FORENSICS_AI_MIN:.0%} "
                "probability range. Insufficient evidence to classify definitively."
            )
            return VERDICT_UNVERIFIED, bullets, True

        # ── Path B: Provenance available ──────────────────────────────
        bullets.append(
            f"Aletheia provenance watermark recovered "
            f"({prov.recovered_regions}/{prov.total_regions} ADPE regions). "
            f"Media ID: {prov.media_id or 'unknown'}."
        )

        if prov.provenance_verdict == VERDICT_AUTHENTIC:
            bullets.append(
                f"Provenance Layer: AUTHENTIC — integrity={prov.integrity_score}/100, "
                f"pHash similarity={prov.similarity:.1f}%, "
                f"Hamming distance={prov.hamming_distance} bits."
            )

            if fore.ai_probability <= _FORENSICS_AUTHENTIC_MAX:
                bullets.append(
                    f"AI Forensics: SUPPORTS authenticity — "
                    f"AI probability={fore.ai_probability:.1%} "
                    f"(verdict: {fore.forensics_verdict}). "
                    "Both layers agree: image is authentic."
                )
                return VERDICT_AUTHENTIC, bullets, True

            # Forensics is ambiguous — provenance takes precedence
            bullets.append(
                f"AI Forensics: AMBIGUOUS ({fore.ai_probability:.1%}). "
                "Provenance evidence takes precedence for the final verdict."
            )
            return VERDICT_AUTHENTIC, bullets, False

        if prov.provenance_verdict == VERDICT_MODIFIED:
            bullets.append(
                f"Provenance Layer: MODIFIED — integrity={prov.integrity_score}/100, "
                f"pHash similarity={prov.similarity:.1f}%. "
                "Image has been visually altered after Aletheia registration."
            )
            if prov.pixel_hash_match is False:
                bullets.append(
                    "Exact pixel integrity check: MISMATCH — the uploaded pixels do not "
                    "match the registered embedded baseline. This confirms a post-embedding "
                    "content change even when the perceptual hash remains highly similar."
                )

            if fore.ai_probability >= _FORENSICS_AI_MIN:
                bullets.append(
                    f"AI Forensics: AI content detected ({fore.ai_probability:.1%}) — "
                    "the modification may have introduced AI-generated content."
                )
                return VERDICT_AI_GENERATED, bullets, True

            return VERDICT_MODIFIED, bullets, True

        # Provenance UNVERIFIED
        bullets.append(
            f"Provenance Layer: UNVERIFIED — "
            f"integrity assessment could not be completed "
            f"({prov.recovered_regions}/{prov.total_regions} regions recovered)."
        )

        if fore.ai_probability >= _FORENSICS_AI_MIN:
            bullets.append(
                f"AI Forensics: AI content detected ({fore.ai_probability:.1%}). "
                "Combined verdict: AI_GENERATED (forensics-led)."
            )
            return VERDICT_AI_GENERATED, bullets, True

        return VERDICT_UNVERIFIED, bullets, False

    # ------------------------------------------------------------------
    # Stage 4: Trust score computation
    # ------------------------------------------------------------------

    def _compute_trust_score(
        self,
        prov: ProvenanceEvidence,
        fore: ForensicsEvidence,
        verdict: str,
    ) -> int:
        """
        Compute a 0–100 trust score from all available evidence.

        Composition:
          Provenance component [0–50]: based on integrity score + pHash similarity.
          Forensics component  [0–50]: based on authenticated probability × confidence.

        Verdict-level floors and caps are applied after score computation to
        ensure the trust score is semantically consistent with the verdict.
        """
        score = 0.0

        # ── Provenance component (0–50 points) ───────────────────────
        if prov.available and prov.integrity_score is not None:
            prov_score = (prov.integrity_score / 100.0) * 45.0

            # Bonus for high pHash similarity (up to +5 points)
            if prov.similarity is not None and prov.similarity >= _SIMILARITY_AUTHENTIC_MIN:
                prov_score = min(prov_score + 5.0, 50.0)

            # Penalty for partial region recovery (proportional to coverage)
            if prov.recovered_regions is not None and prov.total_regions:
                recovery_ratio = prov.recovered_regions / prov.total_regions
                if recovery_ratio < 1.0:
                    prov_score *= (0.5 + 0.5 * recovery_ratio)

            score += prov_score
        # No provenance: zero provenance contribution (forensics carries all weight)

        # ── Forensics component (0–50 points) ────────────────────────
        # Higher authenticity probability → higher forensic trust contribution
        authentic_prob = 1.0 - fore.ai_probability
        fore_score = authentic_prob * 50.0 * fore.confidence
        score += fore_score

        # ── Verdict-level semantic adjustments ────────────────────────
        # Enforce that trust scores are consistent with their verdicts.
        # These are semantic floors/caps, not arbitrary values.
        verdict_adjustments: dict[str, tuple[int, int]] = {
            VERDICT_AUTHENTIC:    (60,  100),  # (floor, cap)
            VERDICT_MODIFIED:     (30,   65),
            VERDICT_AI_GENERATED: (0,    30),
            VERDICT_TAMPERED:     (0,    20),
            VERDICT_SUSPICIOUS:   (15,   35),
            VERDICT_UNVERIFIED:   (10,   45),
        }
        floor, cap = verdict_adjustments.get(verdict, (0, 100))
        score = max(floor, min(cap, score))

        return int(round(score))

    def _score_tampered(self, prov: ProvenanceEvidence) -> int:
        """Trust score for TAMPERED verdict — always critically low."""
        if prov.similarity is not None:
            # Max 15 from similarity (tampered images have very low similarity)
            return int(max(0, min(15, prov.similarity * 0.15)))
        return 5

    def _score_suspicious(
        self, prov: ProvenanceEvidence, fore: ForensicsEvidence
    ) -> int:
        """Trust score for SUSPICIOUS verdict — moderately low."""
        if prov.integrity_score is not None:
            # Provenance is intact but we distrust it: scale down
            base = int(prov.integrity_score * 0.30)
        else:
            base = 20
        return max(15, min(35, base))

    # ------------------------------------------------------------------
    # Stage 5: Confidence computation
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        prov: ProvenanceEvidence,
        fore: ForensicsEvidence,
        layers_agree: bool,
    ) -> float:
        """
        Compute overall engine confidence in the verdict.

        Base confidence comes from the forensics engine.
        Provenance availability significantly boosts confidence.
        Layer agreement adds a bonus; conflict penalizes.
        """
        base = fore.confidence

        if prov.available:
            # Average forensics confidence with a fixed provenance signal strength
            # High integrity → treat as 0.90 provenance signal
            prov_signal = min(
                0.90,
                (prov.integrity_score / 100.0) * 0.90
                if prov.integrity_score is not None else 0.70,
            )
            base = (base + prov_signal) / 2.0
        else:
            # No provenance: penalize confidence
            base = max(base - _CONFIDENCE_NO_PROV_PENALTY, 0.0)

        # Layer agreement adjustment
        if layers_agree:
            base = min(base + _CONFIDENCE_AGREEMENT_BONUS, 1.0)
        else:
            base = max(base - _CONFIDENCE_CONFLICT_PENALTY, 0.0)

        # Penalize for very few contributing detectors
        if fore.detector_count < 2:
            base = max(base - 0.15, 0.0)

        return round(base, 4)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_assessment(
        self,
        verdict: str,
        trust_score: int,
        confidence: float,
        evidence: list[str],
        prov: ProvenanceEvidence,
        fore: ForensicsEvidence,
    ) -> TrustAssessment:
        """Construct a TrustAssessment from all computed components."""
        reasoning = self._build_reasoning(verdict, evidence, prov, fore)
        return TrustAssessment(
            trust_score=trust_score,
            verdict=verdict,
            confidence=confidence,
            reasoning=reasoning,
            provenance_available=prov.available,
            provenance_verdict=prov.provenance_verdict,
            forensics_verdict=fore.forensics_verdict,
            ai_probability=fore.ai_probability,
            integrity_score=prov.integrity_score,
            evidence_summary=list(evidence),
            provenance_evidence=prov,
            forensics_evidence=fore,
        )

    @staticmethod
    def _build_reasoning(
        verdict: str,
        evidence: list[str],
        prov: ProvenanceEvidence,
        fore: ForensicsEvidence,
    ) -> str:
        """
        Build a comprehensive, human-readable reasoning narrative.

        This narrative is suitable for display in a research presentation
        or audit log. It includes all evidence points and layer summaries.
        """
        lines = [
            f"Aletheia Trust & Decision Engine — Final Verdict: {verdict}",
            "=" * 60,
            "",
            "Evidence Chain:",
        ]
        for i, bullet in enumerate(evidence, 1):
            lines.append(f"  [{i}] {bullet}")

        lines.extend([
            "",
            "Layer Summary:",
            f"  Layer 1 (Provenance Engine): "
            + (
                f"Available — Verdict={prov.provenance_verdict}, "
                f"Integrity={prov.integrity_score}/100, "
                f"Similarity={prov.similarity:.1f}%, "
                f"Hamming={prov.hamming_distance}"
                if prov.available and prov.integrity_score is not None
                else "Not available" + (" (MIR recovered but unverified)" if prov.mir_recovered else "")
            ),
            f"  Layer 2 (AI Forensics Engine): "
            f"AI Probability={fore.ai_probability:.1%}, "
            f"Verdict={fore.forensics_verdict}, "
            f"Confidence={fore.confidence:.1%}, "
            f"Detectors={fore.detector_count}",
        ])

        return "\n".join(lines)
