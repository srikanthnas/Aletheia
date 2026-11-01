"""
schemas/verification.py — API I/O contracts for the verification engine.
"""

from pydantic import BaseModel, Field


class VerifyResponse(BaseModel):
    """Response from POST /api/verify."""

    status:           str   = Field(..., examples=["verified"])
    media_id:         str   = Field(..., examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    model_name:       str   = Field(..., examples=["Stable Diffusion XL"])
    timestamp:        str   = Field(..., examples=["2026-07-02T08:00:00+00:00"])
    media_type:       str   = Field(..., examples=["image"])
    framework:        str   = Field(..., examples=["Aletheia"])
    strategy:         str   = Field(..., examples=["sequential_lsb"])
    uploaded_phash:   str   = Field(..., examples=["a3b4c5d6e7f80192"])
    stored_phash:     str   = Field(..., examples=["a3b4c5d6e7f80192"])
    hamming_distance: int   = Field(..., examples=[3])
    similarity:       float = Field(..., examples=[98.43])
    recovered_regions: int   = Field(..., examples=[4])
    total_regions:    int   = Field(..., examples=[4])
    recovery_percentage: float = Field(..., examples=[100.0])
    integrity_score:  int   = Field(..., examples=[100])
    observation:      str   = Field(..., examples=["No tampering detected."])
    verification:     str   = Field(
        ...,
        description="AUTHENTIC | MODIFIED | UNVERIFIED",
        examples=["AUTHENTIC"],
    )
    pixel_hash_match: bool | None = Field(None, description="True when decoded pixels exactly match the registered embedded baseline.")
    uploaded_dhash: str = Field("", description="dHash of submitted image.")
    stored_dhash: str = Field("", description="dHash of registered embedded image.")
    dhash_similarity: float = Field(0.0, description="dHash similarity [0–100].")
    local_similarity: float = Field(0.0, description="Mean local structural similarity [0–100].")
    changed_area_percentage: float = Field(0.0, description="Percentage of comparison regions showing significant local deviation.")
    histogram_distance: float = Field(0.0, description="Normalized grayscale histogram distance.")
    edge_density_delta: float = Field(0.0, description="Absolute edge-density change.")
    high_frequency_ratio: float = Field(1.0, description="High-frequency energy ratio submitted/reference.")
