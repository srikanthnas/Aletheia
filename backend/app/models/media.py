"""
MongoDB document model for the registered_media collection.
Defines the shape of persisted data.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RegisteredMediaDocument(BaseModel):
    """
    Represents one document stored in the `registered_media` collection.
    This is the canonical data model — schemas wrap it for I/O validation.
    """

    image_id: str = Field(..., description="UUID that uniquely identifies the media asset")
    filename: str = Field(..., description="Sanitised original filename")
    model_name: str = Field(..., description="AI model used to generate the image")
    timestamp: str = Field(..., description="ISO-8601 registration timestamp")
    media_type: str = Field(default="image", description="Type of media (image / video / audio)")
    framework_version: str = Field(default="1.0", description="Aletheia framework version")
    upload_path: str = Field(..., description="Relative path to the stored image file")

    class Config:
        populate_by_name = True
