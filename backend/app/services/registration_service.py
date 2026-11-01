"""
Registration Service — core business logic for the Media Registration Engine.

Responsibilities:
  - Validate the uploaded file
  - Persist the image to disk
  - Build the provenance metadata object
  - Store the document in MongoDB
"""

import uuid
import aiofiles
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.models.media import RegisteredMediaDocument
from app.utils.file_utils import is_allowed_extension, build_upload_path
from app.schemas.registration import RegistrationMetadata


SUPPORTED_MODELS = {
    "Stable Diffusion XL",
    "DALL-E",
    "Gemini",
    "Flux",
    "Midjourney",
    "Other",
}


async def register_media(
    file: UploadFile,
    model_name: str,
    db,
) -> RegistrationMetadata:
    """
    Orchestrate the full registration pipeline.

    Steps:
      1. Validate file extension
      2. Validate model name
      3. Generate image_id and timestamp
      4. Save image to disk asynchronously
      5. Build and persist the MongoDB document
      6. Return structured metadata
    """

    # ------------------------------------------------------------------
    # 1. Validate extension
    # ------------------------------------------------------------------
    if not file.filename or not is_allowed_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Accepted: PNG, JPG, JPEG.",
        )

    # ------------------------------------------------------------------
    # 2. Validate model name
    # ------------------------------------------------------------------
    if model_name not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: '{model_name}'. Supported: {sorted(SUPPORTED_MODELS)}",
        )

    # ------------------------------------------------------------------
    # 3. Generate provenance identifiers
    # ------------------------------------------------------------------
    image_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # 4. Persist image to disk
    # ------------------------------------------------------------------
    upload_path = build_upload_path(settings.UPLOAD_DIR, image_id, file.filename)

    contents = await file.read()
    async with aiofiles.open(upload_path, "wb") as out_file:
        await out_file.write(contents)

    # ------------------------------------------------------------------
    # 5. Build MongoDB document
    # ------------------------------------------------------------------
    document = RegisteredMediaDocument(
        image_id=image_id,
        filename=file.filename,
        model_name=model_name,
        timestamp=timestamp,
        media_type="image",
        framework_version=settings.FRAMEWORK_VERSION,
        upload_path=upload_path,
    )

    collection = db["registered_media"]
    await collection.insert_one(document.model_dump())

    # ------------------------------------------------------------------
    # 6. Return metadata
    # ------------------------------------------------------------------
    return RegistrationMetadata(
        image_id=image_id,
        model_name=model_name,
        timestamp=timestamp,
        media_type="image",
        framework_version=settings.FRAMEWORK_VERSION,
    )
