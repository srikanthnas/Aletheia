"""
Pydantic schemas for request/response serialisation.
These are the I/O contracts — separate from the DB model.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RegistrationMetadata(BaseModel):
    """The metadata object returned after successful registration."""

    image_id: str
    model_name: str
    timestamp: str
    media_type: str
    framework_version: str


class RegistrationResponse(BaseModel):
    """Top-level API response for POST /api/register."""

    status: str
    message: str
    metadata: RegistrationMetadata
