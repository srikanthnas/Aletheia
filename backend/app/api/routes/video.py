"""Video provenance API — Aletheia V4 temporal provenance layer."""

import os
import uuid
import aiofiles

from fastapi import (
    APIRouter,
    File,
    Form,
    UploadFile,
    Depends,
    HTTPException,
)
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.connection import get_database
from app.core.config import settings
from app.services.video.video_service import (
    register_video,
    embed_video,
    verify_video,
)

router = APIRouter()


@router.post("/video/register")
async def register_video_endpoint(
    file: UploadFile = File(..., description="Video to register"),
    model_name: str = Form(..., description="AI model used to generate the video"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return {
        "status": "success",
        "metadata": await register_video(file, model_name, db),
    }


@router.post("/video/embed")
async def embed_video_endpoint(
    video_id: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    result = await embed_video(video_id, db)

    # Use a dedicated download endpoint so the browser downloads
    # the authoritative FFV1/MKV artifact instead of attempting
    # browser playback.
    result["download_url"] = f"/api/video/download/{video_id}"

    return {
        "status": "success",
        "result": result,
    }


@router.get("/video/download/{video_id}")
async def download_video_endpoint(
    video_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    record = await db["registered_videos"].find_one(
        {"video_id": video_id},
        {
            "_id": 0,
            "embedded_video_path": 1,
        },
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Registered video not found.",
        )

    video_path = record.get("embedded_video_path")

    if not video_path or not os.path.isfile(video_path):
        raise HTTPException(
            status_code=404,
            detail="Embedded video artifact not found.",
        )

    filename = os.path.basename(video_path)

    return FileResponse(
        path=video_path,
        media_type="video/x-matroska",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/video/verify")
async def verify_video_endpoint(
    file: UploadFile = File(..., description="Video to verify"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    suffix = os.path.splitext(file.filename or ".mp4")[1].lower() or ".mp4"

    temp_name = f"verify_{uuid.uuid4()}{suffix}"

    path = os.path.join(
        settings.UPLOAD_DIR,
        temp_name,
    )

    contents = await file.read()

    try:
        async with aiofiles.open(path, "wb") as out:
            await out.write(contents)

        result = await verify_video(path, db)

        return result

    finally:
        try:
            os.remove(path)
        except OSError:
            pass