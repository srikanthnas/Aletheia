"""
schemas/extraction.py — Request and response schemas for the extraction engine.

These are the API I/O contracts, decoupled from service internals.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested MIR schema (matches MediaIdentityRecord v1.0)
# ---------------------------------------------------------------------------

class RecoveredMIR(BaseModel):
    """The Media Identity Record recovered from an embedded image."""

    mir_version: str  = Field(..., examples=["1.0"])
    media_id:    str  = Field(..., examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    model_name:  str  = Field(..., examples=["Stable Diffusion XL"])
    timestamp:   str  = Field(..., examples=["2026-07-02T08:00:00+00:00"])
    media_type:  str  = Field(..., examples=["image"])
    framework:   str  = Field(..., examples=["Aletheia"])


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class ExtractionResponse(BaseModel):
    """Top-level API response for POST /api/extract."""

    status: str = Field(
        ...,
        description="'success' or 'error'.",
        examples=["success"],
    )
    strategy_used: str = Field(
        ...,
        description="Name of the embedding strategy detected in the image.",
        examples=["sequential_lsb"],
    )
    mir: RecoveredMIR = Field(
        ...,
        description="The Media Identity Record recovered from the embedded image.",
    )
