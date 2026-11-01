"""
Aletheia — AI Media Provenance Framework
Sprint 1: Media Registration Engine
Sprint 2: Provenance Embedding Engine
Sprint 3: Adaptive Provenance Engine
Sprint 4: Provenance Verification Engine
Layer 3:  Trust & Decision Engine

Entry point for the FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.routes import registration, embedding, extraction, verification, dct, forensics, assessment, video
from app.database.connection import connect_to_mongo, close_mongo_connection
from app.core.config import settings

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Aletheia — AI Media Provenance Framework",
    description=(
        "Sprint 1: Media Registration | "
        "Sprint 2: Provenance Embedding | "
        "Sprint 3: Adaptive Provenance Engine | "
        "Sprint 4: Provenance Verification | "
        "Layer 3: Trust & Decision Engine"
    ),
    version="5.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Lifespan events
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()

# ---------------------------------------------------------------------------
# Ensure uploads directory exists (needed before StaticFiles mount)
# ---------------------------------------------------------------------------

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Static file serving (uploaded images)
# ---------------------------------------------------------------------------

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(registration.router,  prefix="/api", tags=["Registration"])
app.include_router(embedding.router,     prefix="/api", tags=["Embedding"])
app.include_router(extraction.router,    prefix="/api", tags=["Extraction"])
app.include_router(verification.router,  prefix="/api", tags=["Verification"])
app.include_router(dct.router,           prefix="/api/dct",        tags=["DCT Experimental"])
app.include_router(forensics.router,     prefix="/api/forensics",  tags=["AI Forensics Engine"])
app.include_router(assessment.router,    prefix="/api",            tags=["Trust & Decision Engine"])
app.include_router(video.router,         prefix="/api",            tags=["Temporal Video Provenance"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "engines": [
            "Media Registration Engine",
            "Provenance Embedding Engine",
            "Adaptive Provenance Engine",
            "Provenance Verification Engine",
            "Trust & Decision Engine",
            "Temporal Video Provenance",
        ],
        "version": "5.0",
    }
