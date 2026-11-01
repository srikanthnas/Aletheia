"""
verification_service.py — Complete provenance verification workflow.

Pipeline:
  1. Extract MIR from uploaded image.
  2. Generate pHash of the uploaded image.
  3. Retrieve stored registration record by media_id.
  4. Retrieve stored pHash.
  5. Compute Hamming Distance.
  6. Compute similarity percentage and integrity assessment.
  7. Perform complementary integrity/tamper analysis.
  8. Return VerificationResult.

The verification layer combines:
  - DCT-QIM/RDM provenance recovery
  - pHash
  - dHash
  - exact pixel fingerprint
  - local perceptual similarity
  - histogram statistics
  - edge-density statistics
  - frequency-domain statistics

Provenance recovery and tamper detection are intentionally separate:
a watermark may survive a transformation while the integrity layer still
detects that the registered media has changed.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image
from fastapi import HTTPException

from app.services.embedding.mir_serializer import MediaIdentityRecord
from app.services.integrity.integrity_service import assess_integrity
from app.services.provenance_extraction_service import extract_provenance
from app.services.verification.hamming_distance import (
    compute_hamming_distance,
    compute_similarity,
)
from app.services.verification.phash_service import generate_phash
from app.services.verification.pixel_hash_service import generate_pixel_hash
from app.services.integrity.integrity_features import (
    dhash_hex,
    hash_similarity,
    local_similarity,
    histogram_distance,
    edge_density,
    high_frequency_energy,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Structured output of the verification pipeline."""

    status: str
    media_id: str
    model_name: str
    timestamp: str
    media_type: str
    framework: str
    strategy: str

    uploaded_phash: str
    stored_phash: str

    hamming_distance: int
    similarity: float

    recovered_regions: int
    total_regions: int
    recovery_percentage: float

    integrity_score: int
    observation: str
    verification: str

    pixel_hash_match: bool | None

    uploaded_dhash: str = ""
    stored_dhash: str = ""
    dhash_similarity: float = 0.0

    local_similarity: float = 0.0
    changed_area_percentage: float = 0.0

    histogram_distance: float = 0.0
    edge_density_delta: float = 0.0
    high_frequency_ratio: float = 1.0

    tamper_type: str = "NONE"
    severity: str = "NONE"


# ---------------------------------------------------------------------------
# Service function
# ---------------------------------------------------------------------------

async def verify_provenance(
    image: Image.Image,
    db,
) -> VerificationResult:
    """
    Execute the full provenance verification pipeline.

    Args:
        image:
            PIL Image of the uploaded potentially embedded media asset.

        db:
            Motor database instance.

    Returns:
        VerificationResult.

    Raises:
        HTTPException 422:
            If no valid MIR is recoverable from the image.

        HTTPException 404:
            If the recovered media_id has no registry entry.

        HTTPException 422:
            If the registry entry has no stored pHash.

        HTTPException 500:
            For unexpected processing failures.
    """

    # ------------------------------------------------------------------
    # 1. Extract MIR using the multi-region provenance pipeline
    # ------------------------------------------------------------------

    try:
        extraction_result = await extract_provenance(
            image,
            db=db,
        )

        mir = extraction_result.mir
        recovered_regions = extraction_result.recovered_regions
        total_regions = extraction_result.total_regions
        inconsistent = extraction_result.inconsistent

    except HTTPException as extraction_error:

        # --------------------------------------------------------------
        # Provenance-loss recovery
        #
        # If an aggressive transformation destroys the embedded MIR,
        # use the registered pHash index to locate the most likely
        # original reference.
        #
        # IMPORTANT:
        # This does NOT declare the submitted image authentic.
        # It only recovers the reference needed for further analysis.
        # --------------------------------------------------------------

        if extraction_error.status_code != 422 or db is None:
            raise

        uploaded_candidate_phash = generate_phash(image)

        best_doc = None
        best_distance = 65

        cursor = db["registered_media"].find(
            {
                "phash": {
                    "$exists": True
                }
            },
            {
                "phash": 1,
                "mir": 1,
                "image_id": 1,
                "model_name": 1,
                "timestamp": 1,
                "media_type": 1,
                "framework_version": 1,
                "embedded_image_path": 1,
            },
        )

        async for candidate in cursor:

            try:
                candidate_phash = candidate.get("phash", "")

                d = compute_hamming_distance(
                    candidate_phash,
                    uploaded_candidate_phash,
                )

            except Exception:
                continue

            if d < best_distance:
                best_distance = d
                best_doc = candidate

            print(f"[Aletheia] Best pHash distance: {best_distance}")

        # No sufficiently similar registered source was found.
        if best_doc is None or best_distance > 18:
            raise extraction_error

        stored_mir = best_doc.get("mir")

        if not stored_mir:
            stored_mir = {
                "mir_version": "1.0",
                "media_id": best_doc.get(
                    "image_id",
                    "UNKNOWN",
                ),
                "model_name": best_doc.get(
                    "model_name",
                    "Unknown",
                ),
                "timestamp": best_doc.get(
                    "timestamp",
                    "",
                ),
                "media_type": best_doc.get(
                    "media_type",
                    "image",
                ),
                "framework": "Aletheia",
            }

        mir = MediaIdentityRecord(
            **stored_mir
        )

        recovered_regions = 0
        total_regions = 1
        inconsistent = False

    # ------------------------------------------------------------------
    # 2. Generate pHash of uploaded image
    # ------------------------------------------------------------------

    try:
        uploaded_phash = generate_phash(image)

    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 3. Retrieve stored registration record
    # ------------------------------------------------------------------

    doc = await db["registered_media"].find_one(
        {
            "image_id": mir.media_id
        }
    )

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No Aletheia registration found for "
                f"media_id='{mir.media_id}'. "
                "The image may have been registered on a "
                "different instance."
            ),
        )

    # ------------------------------------------------------------------
    # 4. Retrieve stored pHash
    # ------------------------------------------------------------------

    stored_phash: str | None = doc.get("phash")

    if not stored_phash:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No pHash stored for media_id='{mir.media_id}'. "
                "Re-embed the image to generate and store "
                "the perceptual hash."
            ),
        )

    # ------------------------------------------------------------------
    # 4a. Determine embedding strategy
    # ------------------------------------------------------------------

    strategy: str = doc.get(
        "embedding_strategy",
        "sequential_lsb",
    )

    # ------------------------------------------------------------------
    # 4b. Exact pixel-level integrity check
    #
    # pHash is intentionally tolerant of mild brightness/contrast
    # changes. Therefore exact pixel hashing is used as an additional
    # integrity signal.
    #
    # Existing registrations are supported by deriving the reference
    # pixel hash from the saved embedded image when necessary.
    # ------------------------------------------------------------------

    pixel_hash_match: bool | None = None

    stored_pixel_hash = doc.get("pixel_hash")

    embedded_path = doc.get(
        "embedded_image_path"
    )

    if not stored_pixel_hash and embedded_path:

        try:
            with Image.open(embedded_path) as baseline_image:
                stored_pixel_hash = generate_pixel_hash(
                    baseline_image
                )

            await db["registered_media"].update_one(
                {
                    "image_id": mir.media_id
                },
                {
                    "$set": {
                        "pixel_hash": stored_pixel_hash
                    }
                },
            )

        except Exception:
            stored_pixel_hash = None

    if stored_pixel_hash:

        try:
            uploaded_pixel_hash = generate_pixel_hash(
                image
            )

            pixel_hash_match = (
                uploaded_pixel_hash == stored_pixel_hash
            )

        except ValueError:
            pixel_hash_match = None

    # ------------------------------------------------------------------
    # 4c. Complementary integrity features
    #
    # These signals are intentionally complementary:
    #
    # pHash:
    #     global perceptual similarity
    #
    # dHash:
    #     gradient/edge-oriented perceptual similarity
    #
    # pixel hash:
    #     exact pixel-level equality
    #
    # local similarity:
    #     localized modifications
    #
    # histogram:
    #     global photometric/color changes
    #
    # edge density:
    #     structural changes
    #
    # high-frequency energy:
    #     blur/noise/sharpening/filter evidence
    # ------------------------------------------------------------------

    uploaded_dhash = dhash_hex(image)

    stored_dhash = str(
        doc.get("dhash", "")
    )

    baseline_image = None

    if embedded_path:

        try:
            baseline_image = (
                Image.open(embedded_path)
                .convert("RGB")
            )

        except Exception:
            baseline_image = None

    # If a reference image cannot be loaded, retain the existing
    # verification path rather than crashing.
    if baseline_image is None:
        baseline_image = image.copy()

    # Generate/store dHash for older registrations.
    if not stored_dhash:

        stored_dhash = dhash_hex(
            baseline_image
        )

        await db["registered_media"].update_one(
            {
                "image_id": mir.media_id
            },
            {
                "$set": {
                    "dhash": stored_dhash
                }
            },
        )

    dhash_sim = hash_similarity(
        stored_dhash,
        uploaded_dhash,
    )

    local_sim, changed_area = local_similarity(
        baseline_image,
        image,
    )

    hist_delta = histogram_distance(
        baseline_image,
        image,
    )

    edge_delta = abs(
        edge_density(baseline_image)
        - edge_density(image)
    )

    ref_hf = high_frequency_energy(
        baseline_image
    )

    cur_hf = high_frequency_energy(
        image
    )

    hf_ratio = (
        cur_hf / ref_hf
        if ref_hf > 1e-9
        else 1.0
    )

    # ------------------------------------------------------------------
    # 5. Compute pHash Hamming distance
    # ------------------------------------------------------------------

    try:

        distance = compute_hamming_distance(
            stored_phash,
            uploaded_phash,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 6. Similarity + Integrity Assessment
    # ------------------------------------------------------------------

    similarity = compute_similarity(
        distance
    )

    assessment = assess_integrity(
        recovered_regions=recovered_regions,
        total_regions=total_regions,
        similarity=similarity,
        hamming_distance=distance,
        inconsistent=inconsistent,
        pixel_hash_match=pixel_hash_match,
        local_similarity=local_sim,
        changed_area_percentage=changed_area,
    )

    # ------------------------------------------------------------------
    # 7. Overall verification status
    # ------------------------------------------------------------------

    overall_status = (
        "verified"
        if assessment.status in (
            "AUTHENTIC",
            "MODIFIED",
        )
        else "unverified"
    )

    recovery_percentage = (
        recovered_regions
        / total_regions
        * 100
        if total_regions > 0
        else 0
    )

    # ------------------------------------------------------------------
    # 8. Return complete verification result
    # ------------------------------------------------------------------

    return VerificationResult(

        status=overall_status,

        media_id=mir.media_id,

        model_name=mir.model_name,

        timestamp=mir.timestamp,

        media_type=mir.media_type,

        framework=mir.framework,

        strategy=strategy,

        uploaded_phash=uploaded_phash,

        stored_phash=stored_phash,

        hamming_distance=distance,

        similarity=similarity,

        recovered_regions=recovered_regions,

        total_regions=total_regions,

        recovery_percentage=round(
            recovery_percentage,
            2,
        ),

        integrity_score=assessment.score,

        observation=assessment.observation,

        verification=assessment.status,

        pixel_hash_match=pixel_hash_match,

        uploaded_dhash=uploaded_dhash,

        stored_dhash=stored_dhash,

        dhash_similarity=round(
            dhash_sim,
            2,
        ),

        local_similarity=round(
            local_sim,
            2,
        ),

        changed_area_percentage=round(
            changed_area,
            2,
        ),

        histogram_distance=round(
            hist_delta,
            6,
        ),

        edge_density_delta=round(
            edge_delta,
            6,
        ),

        high_frequency_ratio=round(
            hf_ratio,
            4,
        ),

        tamper_type=assessment.tamper_type,

        severity=assessment.severity,
    )