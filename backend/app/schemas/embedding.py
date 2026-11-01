"""
schemas/embedding.py — Request and response schemas for the embedding engine.

These are the API I/O contracts, decoupled from both the DB model
and the service return types.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class EmbedRequest(BaseModel):
    """Body for POST /api/embed."""

    image_id: str = Field(
        ...,
        description="UUID of the registered media asset (returned by POST /api/register).",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class EmbedResponse(BaseModel):
    """Top-level API response for POST /api/embed."""

    status: str = Field(..., examples=["success"])
    embedded_image: str = Field(
        ...,
        description="Relative URL to download the provenance-embedded PNG image.",
        examples=["/uploads/3fa85f64-5717-4562-b3fc-2c963f66afa6_embedded.png"],
    )
    embedded_bits: int = Field(
        ...,
        description="Total number of bits written into the carrier image (32-bit header + payload).",
        examples=[1320],
    )
