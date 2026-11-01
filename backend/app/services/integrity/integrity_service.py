"""Multi-signal provenance integrity and tamper assessment."""
from dataclasses import dataclass

@dataclass
class IntegrityAssessment:
    score: int
    observation: str
    status: str
    tamper_type: str = "NONE"
    severity: str = "NONE"


def assess_integrity(
    recovered_regions: int,
    total_regions: int,
    similarity: float,
    hamming_distance: int,
    inconsistent: bool,
    pixel_hash_match: bool | None = None,
    local_similarity: float = 100.0,
    changed_area_percentage: float = 0.0,
) -> IntegrityAssessment:
    """Fuse provenance recovery, pHash and local/exact integrity evidence."""
    recovery_percentage = (recovered_regions / total_regions) * 100 if total_regions else 0.0
    score = float(similarity)
    if pixel_hash_match is False:
        # Exact mismatch proves pixels changed, but not necessarily malicious content.
        score -= 8
    if recovery_percentage < 100:
        score -= ((100 - recovery_percentage) / 100) * 25
    if inconsistent:
        score -= 20
    if local_similarity < 80:
        score -= min(25, (80 - local_similarity) * 0.8)
    score = int(max(0, min(100, round(score))))

    if pixel_hash_match is not False and recovery_percentage >= 100 and similarity >= 90 and hamming_distance <= 8 and not inconsistent:
        return IntegrityAssessment(score, "No post-registration content change detected; provenance is intact.", "AUTHENTIC")

    # A local drop with a still-high global pHash is the signature we want for edits.
    if pixel_hash_match is False and local_similarity < 80:
        return IntegrityAssessment(
            score,
            f"Localized content change detected. {changed_area_percentage:.1f}% of comparison regions show significant deviation.",
            "TAMPERED", "LOCAL_CONTENT_MODIFICATION", "HIGH" if changed_area_percentage >= 10 else "MEDIUM"
        )

    if inconsistent:
        return IntegrityAssessment(score, "Provenance inconsistency detected across distributed regions; selective modification or splicing is likely.", "TAMPERED", "PROVENANCE_INCONSISTENCY", "HIGH")

    if pixel_hash_match is False:
        # High perceptual/local similarity indicates a benign or low-level transformation.
        if similarity >= 85 and local_similarity >= 85:
            if abs(local_similarity - 100) < 5:
                kind = "GLOBAL_PIXEL_TRANSFORMATION"
            else:
                kind = "POST_REGISTRATION_MODIFICATION"
            return IntegrityAssessment(score, "Pixel-level integrity changed while perceptual and local structure remain largely consistent. The media was transformed after registration.", "MODIFIED", kind, "LOW" if similarity >= 95 else "MEDIUM")
        return IntegrityAssessment(score, "Post-registration pixel and perceptual integrity changed. The media no longer matches the registered baseline.", "TAMPERED", "CONTENT_MODIFICATION", "HIGH")

    if recovery_percentage < 100 or similarity < 90 or hamming_distance > 8:
        return IntegrityAssessment(score, "The registered media differs from the submitted image or only partial provenance could be recovered.", "MODIFIED", "STRUCTURAL_MODIFICATION", "MEDIUM")

    return IntegrityAssessment(score, "Minor deviation detected; provenance remains recoverable.", "MODIFIED", "MINOR_MODIFICATION", "LOW")
