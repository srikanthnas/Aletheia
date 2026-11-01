"""
Registration route — POST /api/register

This module is intentionally thin: it delegates all business logic to
the registration service, keeping the route focused on HTTP concerns only.
"""

from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.connection import get_database
from app.services.registration_service import register_media
from app.schemas.registration import RegistrationResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=RegistrationResponse,
    summary="Register a new AI-generated media asset",
    description=(
        "Upload an AI-generated image and record its provenance metadata "
        "into the Aletheia registered_media collection."
    ),
)
async def register_media_endpoint(
    file: UploadFile = File(..., description="AI-generated image (PNG / JPG / JPEG)"),
    model_name: str = Form(..., description="Name of the AI model used to generate the image"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Accepts a multipart/form-data POST with:
      - file       : the image binary
      - model_name : the generative AI model identifier

    Returns a JSON response containing the registered provenance metadata.
    """
    metadata = await register_media(file=file, model_name=model_name, db=db)

    return RegistrationResponse(
        status="success",
        message="Media registered successfully.",
        metadata=metadata,
    )
