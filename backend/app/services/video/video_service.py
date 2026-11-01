"""
Temporal Video Provenance Engine — Aletheia V4.

V4 design:
- Keep the V3 image pipeline untouched.
- Embed one authenticated MIR payload redundantly at deterministic
  temporal checkpoints.
- Each checkpoint is replicated across a +/- 1 frame temporal window.
- Verification measures checkpoint recovery independently from
  temporal perceptual fingerprint integrity.
- FFmpeg is used for media I/O only.
- Watermarking operates on decoded RGB frames.
- Authoritative embedded video is FFV1/lossless.

This is a research implementation and is not a claim of absolute
tamper-proofing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from PIL import Image

from app.core.config import settings
from app.services.dct.robust_codec import (
    HEADER_SIZE,
    decode_header,
    decode_robust,
    encode_robust,
    frame_bit_length,
)
from app.services.embedding.mir_serializer import build_mir, serialize


# ============================================================
# CONFIGURATION
# ============================================================

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
}

SUPPORTED_VIDEO_MODELS = {
    "Stable Diffusion XL",
    "DALL-E",
    "Gemini",
    "Flux",
    "Midjourney",
    "Sora",
    "Runway",
    "Other",
}


# Ten deterministic temporal checkpoints.
#
# These are relative positions in the video:
#
# 5%, 15%, 25%, ..., 95%
#
# The same positions are used during registration, embedding
# and clean-baseline verification.
CHECKPOINT_FRACTIONS = (
    0.05,
    0.15,
    0.25,
    0.35,
    0.45,
    0.55,
    0.65,
    0.75,
    0.85,
    0.95,
)


# Each checkpoint is embedded at:
#
# checkpoint - 1 frame
# checkpoint
# checkpoint + 1 frame
#
# This gives 3-frame redundancy per checkpoint.
TEMPORAL_WINDOW_RADIUS = 1


# Video-specific DCT watermark.
#
# IMPORTANT:
# This is NOT the V3 image QIM/RDM implementation.
# It uses DCT coefficient polarity modulation.
VIDEO_WATERMARK_POSITIONS = (
    (1, 1),
    (1, 2),
    (2, 1),
    (0, 2),
    (2, 0),
    (2, 2),
)

VIDEO_WATERMARK_STRENGTH = 36.0


# pHash threshold used for checkpoint-level integrity comparison.
PHASH_MATCH_THRESHOLD = 18


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class VideoInfo:
    duration: float
    fps: float
    frame_count: int
    width: int
    height: int
    has_audio: bool


# ============================================================
# FFMPEG HELPERS
# ============================================================

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """
    Run a subprocess and convert FFmpeg failures into readable errors.
    """

    try:
        return subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )

    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFmpeg/FFprobe is required for Aletheia video provenance. "
            "Install FFmpeg and ensure ffmpeg and ffprobe are on PATH."
        ) from exc

    except subprocess.CalledProcessError as exc:
        detail = (
            exc.stderr
            or exc.stdout
            or "FFmpeg command failed"
        ).strip()

        raise RuntimeError(detail[-3000:]) from exc


def _probe(path: str) -> VideoInfo:
    """
    Read video metadata using ffprobe.
    """

    result = _run([
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        path,
    ])

    data = json.loads(result.stdout)

    streams = data.get("streams", [])

    video = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
        ),
        None,
    )

    if not video:
        raise ValueError(
            "Uploaded file does not contain a video stream."
        )

    def fraction(
        value: str | None,
        fallback: float = 0.0,
    ) -> float:

        if not value or value in {"0/0", "N/A"}:
            return fallback

        try:
            a, b = value.split("/")

            numerator = float(a)
            denominator = float(b)

            if denominator == 0:
                return fallback

            return numerator / denominator

        except Exception:

            try:
                return float(value)

            except Exception:
                return fallback

    fps = fraction(
        video.get("avg_frame_rate")
        or video.get("r_frame_rate"),
        0.0,
    )

    duration = float(
        video.get("duration")
        or data.get("format", {}).get("duration")
        or 0
    )

    frame_count = int(
        video.get("nb_frames")
        or round(duration * fps)
    )

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)

    has_audio = any(
        stream.get("codec_type") == "audio"
        for stream in streams
    )

    if (
        duration <= 0
        or fps <= 0
        or width < 16
        or height < 16
    ):
        raise ValueError(
            "Could not determine valid video duration, FPS, "
            "or dimensions."
        )

    if frame_count <= 0:
        frame_count = max(
            1,
            round(duration * fps),
        )

    return VideoInfo(
        duration=duration,
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
        has_audio=has_audio,
    )


# ============================================================
# TEMPORAL CHECKPOINTS
# ============================================================

def _checkpoint_frames(
    info: VideoInfo,
) -> list[int]:
    """
    Convert deterministic checkpoint fractions into integer
    frame indices.

    Example for a 300-frame video:

        5%  -> frame 15
        15% -> frame 45
        ...
        95% -> frame 285
    """

    return sorted({
        max(
            0,
            min(
                info.frame_count - 1,
                int(
                    round(
                        info.duration
                        * fraction
                        * info.fps
                    )
                ),
            ),
        )
        for fraction in CHECKPOINT_FRACTIONS
    })


def _checkpoint_frame_window(
    info: VideoInfo,
    checkpoint_number: int,
) -> list[int]:
    """
    Return the +/-1 frame window around one checkpoint.

    checkpoint_number is zero-based.
    """

    checkpoint_frames = _checkpoint_frames(info)

    if checkpoint_number < 0:
        return []

    if checkpoint_number >= len(checkpoint_frames):
        return []

    center = checkpoint_frames[checkpoint_number]

    return [
        index
        for index in range(
            max(
                0,
                center - TEMPORAL_WINDOW_RADIUS,
            ),
            min(
                info.frame_count,
                center + TEMPORAL_WINDOW_RADIUS + 1,
            ),
        )
    ]


# ============================================================
# FRAME EXTRACTION
# ============================================================

def _extract_all_frames(
    video_path: str,
    output_dir: str,
) -> list[str]:
    """
    Decode the complete video into numbered PNG frames.

    Verification intentionally uses integer frame indices rather
    than FFmpeg timestamp seeking for deterministic checkpoint
    verification.
    """

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    _run([
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        video_path,
        "-start_number",
        "0",
        os.path.join(
            output_dir,
            "%08d.png",
        ),
    ])

    return sorted(
        os.path.join(
            output_dir,
            filename,
        )
        for filename in os.listdir(output_dir)
        if filename.lower().endswith(".png")
    )


def _extract_selected_frames(
    video_path: str,
    output_dir: str,
    times: list[float],
) -> list[str]:
    """
    Extract selected frames using timestamps.

    This is used only for broad fallback discovery.
    It is NOT used for deterministic checkpoint recovery.
    """

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    paths: list[str] = []

    for index, timestamp in enumerate(times):

        output_path = os.path.join(
            output_dir,
            f"probe_{index:04d}.png",
        )

        _run([
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{max(0.0, timestamp):.6f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-f",
            "image2",
            output_path,
        ])

        paths.append(output_path)

    return paths


# ============================================================
# VIDEO DCT WATERMARK
# ============================================================

def _embed_frame(
    image: Image.Image,
    bits: list[int],
) -> Image.Image:
    """
    Embed one robust provenance payload into a decoded RGB frame.

    Each bit is represented by the polarity of selected
    mid-frequency DCT coefficients.

    This implementation is intentionally video-specific and
    does not modify the V3 image watermark implementation.
    """

    from app.services.dct.block_processor import (
        get_blocks_8x8,
        get_ycbcr_channels,
        reconstruct_image,
        reconstruct_y_channel,
    )

    from app.services.dct.dct_transform import (
        forward_dct_8x8,
        inverse_dct_8x8,
    )

    y, cb, cr = get_ycbcr_channels(
        image.convert("RGB")
    )

    blocks = list(
        get_blocks_8x8(y)
    )

    capacity = (
        len(blocks)
        * len(VIDEO_WATERMARK_POSITIONS)
    )

    if len(bits) > capacity:
        raise ValueError(
            f"Video temporal watermark capacity "
            f"({capacity} bits) is below payload size "
            f"({len(bits)} bits)."
        )

    processed_blocks = []

    bit_index = 0

    for block_index, block in enumerate(blocks):

        dct_block = forward_dct_8x8(
            block - 128.0
        )

        for row, column in VIDEO_WATERMARK_POSITIONS:

            if bit_index >= len(bits):
                break

            source = float(
                dct_block[row, column]
            )

            desired_bit = bits[bit_index]

            target = (
                VIDEO_WATERMARK_STRENGTH
                if desired_bit == 0
                else -VIDEO_WATERMARK_STRENGTH
            )

            if abs(source) > VIDEO_WATERMARK_STRENGTH:

                if desired_bit == 0:
                    dct_block[row, column] = abs(source)
                else:
                    dct_block[row, column] = -abs(source)

            else:

                dct_block[row, column] = target

            bit_index += 1

        processed_blocks.append(
            inverse_dct_8x8(
                dct_block
            ) + 128.0
        )

        if bit_index >= len(bits):

            # Preserve every block after the payload.
            processed_blocks.extend(
                blocks[block_index + 1:]
            )

            break

    return reconstruct_image(
        reconstruct_y_channel(
            processed_blocks,
            y,
        ),
        cb,
        cr,
    )


def _extract_frame_bits(
    image: Image.Image,
    bit_count: int,
) -> list[int]:
    """
    Extract a specified number of watermark bits from one frame.
    """

    from app.services.dct.block_processor import (
        get_blocks_8x8,
        get_ycbcr_channels,
    )

    from app.services.dct.dct_transform import (
        forward_dct_8x8,
    )

    y, _, _ = get_ycbcr_channels(
        image.convert("RGB")
    )

    blocks = list(
        get_blocks_8x8(y)
    )

    capacity = (
        len(blocks)
        * len(VIDEO_WATERMARK_POSITIONS)
    )

    if bit_count > capacity:
        raise ValueError(
            "Video frame is too small to carry "
            "the expected provenance frame."
        )

    bits: list[int] = []

    for block in blocks:

        dct_block = forward_dct_8x8(
            block - 128.0
        )

        for row, column in VIDEO_WATERMARK_POSITIONS:

            if len(bits) >= bit_count:
                return bits

            bits.append(
                int(
                    float(
                        dct_block[row, column]
                    ) < 0
                )
            )

    return bits


# ============================================================
# ROBUST PROVENANCE DECODING
# ============================================================

def _decode_provenance_from_frame(
    image: Image.Image,
) -> tuple[dict, dict]:
    """
    Decode the MIR provenance payload from one frame.

    The robust codec provides the header, payload length,
    Hamming correction and CRC validation.
    """

    # The existing robust codec uses 14 encoded bits per raw byte.
    header_bits = HEADER_SIZE * 14

    header = _extract_frame_bits(
        image,
        header_bits,
    )

    _, payload_length, _, _ = decode_header(
        header
    )

    total_bits = frame_bit_length(
        payload_length
    )

    bits = _extract_frame_bits(
        image,
        total_bits,
    )

    payload, meta = decode_robust(
        bits
    )

    mir = json.loads(
        payload.decode("utf-8")
    )

    if not isinstance(mir, dict):
        raise ValueError(
            "Decoded provenance payload is not a JSON object."
        )

    return mir, meta


# ============================================================
# PERCEPTUAL FINGERPRINT
# ============================================================

def _frame_phash(
    image: Image.Image,
) -> str | None:

    try:

        from app.services.verification.phash_service import (
            generate_phash,
        )

        return generate_phash(image)

    except Exception:

        # Self-contained DCT pHash fallback.
        try:

            import numpy as np
            from scipy.fftpack import dct

            gray = np.asarray(
                image.convert("L").resize(
                    (32, 32)
                ),
                dtype=np.float32,
            )

            coefficients = dct(
                dct(
                    gray,
                    axis=0,
                    norm="ortho",
                ),
                axis=1,
                norm="ortho",
            )[:8, :8]

            low_frequency = coefficients.flatten()

            median = float(
                np.median(
                    low_frequency[1:]
                )
            )

            value = 0

            for coefficient in low_frequency:

                value = (
                    value << 1
                ) | int(
                    coefficient > median
                )

            return f"{value:016x}"

        except Exception:

            return None


def _phash_distance(
    first: str,
    second: str,
) -> int:

    try:

        return (
            int(first, 16)
            ^ int(second, 16)
        ).bit_count()

    except Exception:

        return 64


# ============================================================
# BROAD PHASH SOURCE DISCOVERY
# ============================================================

def _temporal_fingerprint_score(
    current_hashes: list[str],
    registered_hashes: list[str],
    threshold: int = 16,
) -> dict:
    """
    Broad temporal fingerprint score.

    IMPORTANT:

    This is used only when embedded provenance is unavailable
    and the system is attempting source identification.

    It is NOT the primary integrity calculation.

    Each current frame is compared with its nearest registered
    checkpoint.
    """

    if not current_hashes or not registered_hashes:

        return {
            "matches": 0,
            "total": len(current_hashes),
            "match_rate": 0.0,
            "mean_distance": 64.0,
            "distances": [],
        }

    distances = []

    for current_hash in current_hashes:

        distance = min(
            _phash_distance(
                current_hash,
                reference_hash,
            )
            for reference_hash in registered_hashes
        )

        distances.append(
            distance
        )

    matches = sum(
        distance <= threshold
        for distance in distances
    )

    return {
        "matches": matches,
        "total": len(distances),
        "match_rate": round(
            matches / len(distances),
            4,
        ),
        "mean_distance": round(
            sum(distances)
            / len(distances),
            3,
        ),
        "distances": distances,
    }


# ============================================================
# CHECKPOINT-ALIGNED PHASH
# ============================================================

def _aligned_checkpoint_fingerprint_score(
    frame_paths: list[str],
    info: VideoInfo,
    registered_fingerprints: list[dict],
    threshold: int = PHASH_MATCH_THRESHOLD,
) -> dict:
    """
    Compare registered temporal fingerprints with the SAME
    deterministic temporal checkpoints in the current video.

    Each checkpoint is allowed a +/-1 frame local search.

    This is the critical difference from the old implementation.

    OLD:

        arbitrary current frame
             ↓
        nearest arbitrary registered checkpoint

    NEW:

        checkpoint 1 → checkpoint 1
        checkpoint 2 → checkpoint 2
        ...
        checkpoint 10 → checkpoint 10
    """

    total_checkpoints = len(
        CHECKPOINT_FRACTIONS
    )

    if not frame_paths or not registered_fingerprints:

        return {
            "matches": 0,
            "total": total_checkpoints,
            "match_rate": 0.0,
            "mean_distance": 64.0,
            "distances": [],
            "checkpoint_results": [],
        }

    checkpoint_frames = _checkpoint_frames(
        info
    )

    checkpoint_results = []

    for checkpoint_index, fraction in enumerate(
        CHECKPOINT_FRACTIONS
    ):

        reference = (
            registered_fingerprints[
                checkpoint_index
            ]
            if checkpoint_index
            < len(registered_fingerprints)
            else {}
        )

        reference_hash = reference.get(
            "phash"
        )

        if checkpoint_index < len(
            checkpoint_frames
        ):
            expected_frame_index = (
                checkpoint_frames[
                    checkpoint_index
                ]
            )
        else:
            expected_frame_index = 0

        candidate_indices = range(
            max(
                0,
                expected_frame_index
                - TEMPORAL_WINDOW_RADIUS,
            ),
            min(
                len(frame_paths),
                expected_frame_index
                + TEMPORAL_WINDOW_RADIUS
                + 1,
            ),
        )

        best_distance = 64
        best_frame_index = None

        if reference_hash:

            for frame_index in candidate_indices:

                try:

                    with Image.open(
                        frame_paths[
                            frame_index
                        ]
                    ) as image:

                        current_hash = _frame_phash(
                            image
                        )

                    if not current_hash:
                        continue

                    distance = _phash_distance(
                        current_hash,
                        reference_hash,
                    )

                    if distance < best_distance:

                        best_distance = distance
                        best_frame_index = frame_index

                except Exception:

                    continue

        matched = (
            best_distance <= threshold
        )

        checkpoint_results.append({
            "checkpoint": checkpoint_index + 1,
            "fraction": fraction,
            "registered_time_seconds": round(
                info.duration * fraction,
                4,
            ),
            "registered_frame_index": (
                expected_frame_index
            ),
            "observed_frame_index": (
                best_frame_index
            ),
            "distance": best_distance,
            "matched": matched,
        })

    distances = [
        result["distance"]
        for result in checkpoint_results
    ]

    matches = sum(
        result["matched"]
        for result in checkpoint_results
    )

    total = len(
        checkpoint_results
    )

    return {
        "matches": matches,
        "total": total,
        "match_rate": round(
            matches / total,
            4,
        ) if total else 0.0,
        "mean_distance": round(
            sum(distances)
            / len(distances),
            3,
        ) if distances else 64.0,
        "distances": distances,
        "checkpoint_results": checkpoint_results,
    }


# ============================================================
# TAMPER WINDOW REPORTING
# ============================================================

def _tamper_windows(
    checkpoint_results: list[dict],
) -> list[dict]:
    """
    Convert checkpoint pHash mismatches into temporal observations.
    """

    return [
        {
            "checkpoint": result[
                "checkpoint"
            ],
            "fraction": result[
                "fraction"
            ],
            "time_seconds": result[
                "registered_time_seconds"
            ],
            "phash_distance": result[
                "distance"
            ],
        }
        for result in checkpoint_results
        if not result.get(
            "matched",
            False,
        )
    ]


# ============================================================
# CHECKPOINT PROVENANCE RECOVERY
# ============================================================

def _recover_checkpoint_provenance(
    frame_paths: list[str],
    info: VideoInfo,
    expected_media_id: str | None = None,
) -> dict:
    """
    Recover provenance independently for every deterministic
    checkpoint.

    A checkpoint is considered recovered when at least ONE frame
    inside its +/-1 temporal redundancy window produces a valid
    robust MIR payload.

    If expected_media_id is supplied, the recovered payload must
    reference that exact media ID.
    """

    checkpoint_frames = _checkpoint_frames(
        info
    )

    results = []

    for checkpoint_index, fraction in enumerate(
        CHECKPOINT_FRACTIONS
    ):

        recovered = False
        recovered_frame_index = None
        recovered_media_id = None
        errors = 0

        candidate_indices = _checkpoint_frame_window(
            info,
            checkpoint_index,
        )

        for frame_index in candidate_indices:

            if frame_index >= len(frame_paths):
                continue

            try:

                with Image.open(
                    frame_paths[
                        frame_index
                    ]
                ) as image:

                    mir, _ = _decode_provenance_from_frame(
                        image
                    )

                media_id = str(
                    mir.get(
                        "media_id",
                        "",
                    )
                )

                if not media_id:
                    continue

                if (
                    expected_media_id is not None
                    and media_id != expected_media_id
                ):
                    continue

                recovered = True
                recovered_frame_index = frame_index
                recovered_media_id = media_id

                break

            except Exception:

                errors += 1

        center_frame = (
            checkpoint_frames[
                checkpoint_index
            ]
            if checkpoint_index
            < len(checkpoint_frames)
            else None
        )

        results.append({
            "checkpoint": checkpoint_index + 1,
            "fraction": fraction,
            "time_seconds": round(
                info.duration * fraction,
                4,
            ),
            "frame_index": center_frame,
            "recovered": recovered,
            "recovered_frame_index": (
                recovered_frame_index
            ),
            "media_id": recovered_media_id,
            "errors": errors,
        })

    recovered_count = sum(
        result["recovered"]
        for result in results
    )

    checkpoint_count = len(
        results
    )

    return {
        "recovered_checkpoints": recovered_count,
        "checkpoint_count": checkpoint_count,
        "recovery_percentage": round(
            100.0
            * recovered_count
            / checkpoint_count,
            2,
        ) if checkpoint_count else 0.0,
        "checkpoint_results": results,
    }


# ============================================================
# VIDEO REGISTRATION
# ============================================================

async def register_video(
    file,
    model_name: str,
    db,
) -> dict:

    if (
        not file.filename
        or os.path.splitext(
            file.filename
        )[1].lower()
        not in VIDEO_EXTENSIONS
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported video type. "
                "Accepted: MP4, MOV, MKV, WEBM, AVI, M4V."
            ),
        )

    if model_name not in SUPPORTED_VIDEO_MODELS:

        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: '{model_name}'.",
        )

    video_id = str(
        uuid.uuid4()
    )

    from datetime import datetime, timezone

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    extension = os.path.splitext(
        file.filename
    )[1].lower()

    path = os.path.join(
        settings.UPLOAD_DIR,
        f"{video_id}_original{extension}",
    )

    contents = await file.read()

    with open(
        path,
        "wb",
    ) as output:

        output.write(
            contents
        )

    try:

        info = _probe(
            path
        )

    except Exception as exc:

        if os.path.exists(path):
            os.remove(path)

        raise HTTPException(
            status_code=400,
            detail=f"Invalid video: {exc}",
        )

    checkpoints = _checkpoint_frames(
        info
    )

    if len(checkpoints) != len(
        CHECKPOINT_FRACTIONS
    ):

        if os.path.exists(path):
            os.remove(path)

        raise HTTPException(
            status_code=400,
            detail=(
                "Video is too short for the "
                f"{len(CHECKPOINT_FRACTIONS)}-checkpoint "
                "temporal provenance layout."
            ),
        )

    fingerprint_dir = tempfile.mkdtemp(
        prefix="aletheia_video_register_"
    )

    try:

        checkpoint_times = [
            fraction * info.duration
            for fraction in CHECKPOINT_FRACTIONS
        ]

        fingerprint_paths = (
            _extract_selected_frames(
                path,
                fingerprint_dir,
                checkpoint_times,
            )
        )

        temporal_fingerprints = []

        for (
            fraction,
            timestamp_seconds,
            fingerprint_path,
        ) in zip(
            CHECKPOINT_FRACTIONS,
            checkpoint_times,
            fingerprint_paths,
        ):

            with Image.open(
                fingerprint_path
            ) as frame:

                phash = _frame_phash(
                    frame
                )

            temporal_fingerprints.append({
                "fraction": fraction,
                "time_seconds": round(
                    timestamp_seconds,
                    4,
                ),
                "phash": phash,
            })

    finally:

        shutil.rmtree(
            fingerprint_dir,
            ignore_errors=True,
        )

    document = {
        "video_id": video_id,
        "filename": file.filename,
        "model_name": model_name,
        "timestamp": timestamp,
        "media_type": "video",
        "framework_version": settings.FRAMEWORK_VERSION,

        "upload_path": path,

        "duration": info.duration,
        "fps": info.fps,
        "frame_count": info.frame_count,
        "width": info.width,
        "height": info.height,

        "checkpoint_frames": checkpoints,
        "checkpoint_fractions": list(
            CHECKPOINT_FRACTIONS
        ),

        "temporal_fingerprints": (
            temporal_fingerprints
        ),
    }

    await db[
        "registered_videos"
    ].insert_one(
        document
    )

    return {
        key: value
        for key, value in document.items()
        if key not in {
            "upload_path",
            "_id",
        }
    }


# ============================================================
# VIDEO EMBEDDING
# ============================================================

async def embed_video(
    video_id: str,
    db,
) -> dict:

    document = await db[
        "registered_videos"
    ].find_one({
        "video_id": video_id
    })

    if not document:

        raise HTTPException(
            status_code=404,
            detail=(
                "No registered video with "
                f"video_id='{video_id}'."
            ),
        )

    original = document[
        "upload_path"
    ]

    if not os.path.exists(
        original
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                "Registered video file is missing."
            ),
        )

    # --------------------------------------------------------
    # Build MIR
    # --------------------------------------------------------

    mir = build_mir(
        media_id=video_id,
        model_name=document[
            "model_name"
        ],
        timestamp=document[
            "timestamp"
        ],
        media_type="video",
        mir_version="1.1",
    )

    payload = serialize(
        mir
    )

    # V3 robust codec:
    #
    # payload
    #   ↓
    # Hamming(7,4)
    #   ↓
    # CRC32
    #   ↓
    # interleaving
    #   ↓
    # bitstream
    bits = encode_robust(
        payload
    )

    info = _probe(
        original
    )

    work = tempfile.mkdtemp(
        prefix="aletheia_video_embed_"
    )

    frames_dir = os.path.join(
        work,
        "frames",
    )

    try:

        # ----------------------------------------------------
        # Decode all source frames
        # ----------------------------------------------------

        frame_files = _extract_all_frames(
            original,
            frames_dir,
        )

        if not frame_files:

            raise RuntimeError(
                "FFmpeg produced no video frames."
            )

        # ----------------------------------------------------
        # Determine deterministic checkpoints
        # ----------------------------------------------------

        checkpoint_frames = (
            document.get(
                "checkpoint_frames"
            )
            or _checkpoint_frames(info)
        )

        if len(checkpoint_frames) != len(
            CHECKPOINT_FRACTIONS
        ):

            raise RuntimeError(
                "Registered video does not contain "
                "the expected ten temporal checkpoints."
            )

        # ----------------------------------------------------
        # Expand every checkpoint to +/-1 frame
        # ----------------------------------------------------

        embedded_indices = sorted({
            max(
                0,
                min(
                    len(frame_files) - 1,
                    checkpoint_frame
                    + delta,
                ),
            )
            for checkpoint_frame
            in checkpoint_frames
            for delta in (
                -TEMPORAL_WINDOW_RADIUS,
                0,
                TEMPORAL_WINDOW_RADIUS,
            )
        })

        # ----------------------------------------------------
        # Embed the same authenticated payload into each
        # temporal redundancy frame.
        # ----------------------------------------------------

        for frame_index in embedded_indices:

            with Image.open(
                frame_files[
                    frame_index
                ]
            ) as image:

                embedded = _embed_frame(
                    image,
                    bits,
                )

                embedded.save(
                    frame_files[
                        frame_index
                    ],
                    "PNG",
                    optimize=False,
                )

        embedded_frame_count = len(
            embedded_indices
        )

        checkpoint_count = len(
            checkpoint_frames
        )

        if checkpoint_count != 10:

            raise RuntimeError(
                f"Expected 10 checkpoints, "
                f"found {checkpoint_count}."
            )

        if embedded_frame_count < checkpoint_count:

            raise RuntimeError(
                "Too few temporal frames were available "
                "for provenance embedding."
            )

        # ----------------------------------------------------
        # Encode authoritative lossless video
        # ----------------------------------------------------

        output_name = (
            f"{video_id}_aletheia_v4.mkv"
        )

        output_path = os.path.join(
            settings.UPLOAD_DIR,
            output_name,
        )

        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",

            "-framerate",
            f"{info.fps:.12f}",

            "-start_number",
            "0",

            "-i",
            os.path.join(
                frames_dir,
                "%08d.png",
            ),

            "-i",
            original,

            "-map",
            "0:v:0",

            "-map",
            "1:a?",

            # Lossless authoritative video.
            "-c:v",
            "ffv1",

            "-level",
            "3",

            "-coder",
            "1",

            "-context",
            "1",

            "-g",
            "1",

            "-pix_fmt",
            "gbrp",

            # Preserve original audio.
            "-c:a",
            "copy",

            "-shortest",

            output_path,
        ]

        _run(
            command
        )

        # ----------------------------------------------------
        # Persist embedding metadata
        # ----------------------------------------------------

        await db[
            "registered_videos"
        ].update_one(
            {
                "video_id": video_id
            },
            {
                "$set": {
                    "embedded_video_path": output_path,

                    "embedded_bits": len(
                        bits
                    ),

                    "embedding_strategy":
                        "temporal_dct_polarity_v1",

                    "checkpoint_count":
                        checkpoint_count,

                    "embedded_frame_count":
                        embedded_frame_count,

                    "embedded_frame_indices":
                        embedded_indices,

                    "provenance_payload_bytes":
                        len(payload),
                }
            },
        )

        return {
            "video_id": video_id,

            "download_url":
                f"/uploads/{output_name}",

            "embedded_bits":
                len(bits),

            "checkpoint_count":
                checkpoint_count,

            "embedded_frame_count":
                embedded_frame_count,

            "strategy":
                "temporal_dct_polarity_v1",

            "codec":
                "FFV1/gbrp",
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Video embedding failed: {exc}"
            ),
        )

    finally:

        shutil.rmtree(
            work,
            ignore_errors=True,
        )


# ============================================================
# BROAD WATERMARK DISCOVERY
# ============================================================

async def _discover_provenance(
    video_file_path: str,
    info: VideoInfo,
) -> dict | None:
    """
    Search a broad temporal grid for a recoverable MIR.

    This is NOT the clean-baseline checkpoint verifier.

    It exists for cases such as:
    - trimming
    - temporal shifts
    - loss of exact checkpoint alignment
    """

    scan_count = min(
        48,
        max(
            20,
            int(
                info.duration * 10
            ),
        ),
    )

    times = [
        info.duration
        * (index + 0.5)
        / scan_count
        for index in range(
            scan_count
        )
    ]

    work = tempfile.mkdtemp(
        prefix="aletheia_video_discovery_"
    )

    try:

        paths = _extract_selected_frames(
            video_file_path,
            work,
            times,
        )

        candidates = []

        for index, path in enumerate(
            paths
        ):

            try:

                with Image.open(
                    path
                ) as image:

                    mir, meta = (
                        _decode_provenance_from_frame(
                            image
                        )
                    )

                media_id = str(
                    mir.get(
                        "media_id",
                        "",
                    )
                )

                if not media_id:
                    continue

                candidates.append({
                    "scan_index": index,
                    "time": times[index],
                    "mir": mir,
                    "meta": meta,
                })

            except Exception:

                continue

        if not candidates:

            return None

        groups: dict[
            str,
            list[dict]
        ] = {}

        for candidate in candidates:

            media_id = str(
                candidate[
                    "mir"
                ][
                    "media_id"
                ]
            )

            groups.setdefault(
                media_id,
                [],
            ).append(
                candidate
            )

        media_id, group = max(
            groups.items(),
            key=lambda item: len(
                item[1]
            ),
        )

        return {
            "media_id": media_id,
            "group": group,
            "times": times,
            "paths": paths,
        }

    finally:

        shutil.rmtree(
            work,
            ignore_errors=True,
        )


# ============================================================
# VIDEO VERIFICATION
# ============================================================

async def verify_video(
    video_file_path: str,
    db,
) -> dict:

    if not os.path.exists(
        video_file_path
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Video file could not be read."
            ),
        )

    try:

        info = _probe(
            video_file_path
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=f"Invalid video: {exc}",
        )

    work = tempfile.mkdtemp(
        prefix="aletheia_video_verify_"
    )

    try:

        # ====================================================
        # STEP 1
        # Decode complete video.
        #
        # This gives verification the exact same integer
        # frame coordinate system used during embedding.
        # ====================================================

        frame_paths = _extract_all_frames(
            video_file_path,
            work,
        )

        if not frame_paths:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No video frames could be decoded."
                ),
            )

        # ====================================================
        # STEP 2
        # Deterministic checkpoint provenance recovery.
        #
        # This is the PRIMARY V4 verification path.
        # ====================================================

        checkpoint_probe = (
            _recover_checkpoint_provenance(
                frame_paths,
                info,
                expected_media_id=None,
            )
        )

        # ----------------------------------------------------
        # Determine which media_id was recovered most often.
        # ----------------------------------------------------

        recovered_media_ids: dict[
            str,
            int
        ] = {}

        for checkpoint in (
            checkpoint_probe[
                "checkpoint_results"
            ]
        ):

            if (
                checkpoint.get(
                    "recovered"
                )
                and checkpoint.get(
                    "media_id"
                )
            ):

                media_id = str(
                    checkpoint[
                        "media_id"
                    ]
                )

                recovered_media_ids[
                    media_id
                ] = (
                    recovered_media_ids.get(
                        media_id,
                        0,
                    )
                    + 1
                )

        dominant_media_id = None

        if recovered_media_ids:

            dominant_media_id = max(
                recovered_media_ids,
                key=recovered_media_ids.get,
            )

        # ====================================================
        # STEP 3
        # Re-run checkpoint verification using the dominant
        # media_id.
        #
        # This prevents a foreign provenance payload from
        # being counted as valid provenance for the source.
        # ====================================================

        if dominant_media_id:

            checkpoint_probe = (
                _recover_checkpoint_provenance(
                    frame_paths,
                    info,
                    expected_media_id=dominant_media_id,
                )
            )

            registry = await db[
                "registered_videos"
            ].find_one({
                "video_id":
                    dominant_media_id
            })

            # ------------------------------------------------
            # Recover MIR consistency across checkpoints.
            # ------------------------------------------------

            reference_mir = None
            consistent = True

            for checkpoint in (
                checkpoint_probe[
                    "checkpoint_results"
                ]
            ):

                if not checkpoint.get(
                    "recovered"
                ):

                    continue

                frame_index = checkpoint.get(
                    "recovered_frame_index"
                )

                if frame_index is None:
                    continue

                if frame_index >= len(
                    frame_paths
                ):

                    continue

                try:

                    with Image.open(
                        frame_paths[
                            frame_index
                        ]
                    ) as image:

                        mir, _ = (
                            _decode_provenance_from_frame(
                                image
                            )
                        )

                    if reference_mir is None:

                        reference_mir = mir

                    elif mir != reference_mir:

                        consistent = False

                except Exception:

                    consistent = False

            # =================================================
            # REGISTERED SOURCE
            # =================================================

            if registry:

                registered_fingerprints = (
                    registry.get(
                        "temporal_fingerprints",
                        [],
                    )
                )

                # ---------------------------------------------
                # IMPORTANT:
                #
                # This is aligned checkpoint pHash comparison.
                # ---------------------------------------------

                fingerprint_score = (
                    _aligned_checkpoint_fingerprint_score(
                        frame_paths,
                        info,
                        registered_fingerprints,
                    )
                )

                duration_delta = abs(
                    float(
                        registry.get(
                            "duration",
                            0.0,
                        )
                    )
                    - info.duration
                )

                geometry_match = (
                    int(
                        registry.get(
                            "width",
                            0,
                        )
                    )
                    == info.width
                    and
                    int(
                        registry.get(
                            "height",
                            0,
                        )
                    )
                    == info.height
                )

                recovery_rate = (
                    checkpoint_probe[
                        "recovery_percentage"
                    ]
                    / 100.0
                )

                fingerprint_match_rate = (
                    fingerprint_score[
                        "match_rate"
                    ]
                )

                fingerprint_mean_distance = (
                    fingerprint_score[
                        "mean_distance"
                    ]
                )

                # -------------------------------------------------------------
                # STRICT CLEAN-INTEGRITY GATE
                #
                # Provenance recovery and source identification are not the same
                # as proving that the submitted media is unchanged.
                #
                # A partial checkpoint match such as 8/10 must NEVER be
                # sufficient for a clean/authentic result.
                # -------------------------------------------------------------

                full_provenance_recovery = (
                    recovery_rate >= 1.0
                )

                full_temporal_alignment = (
                    fingerprint_match_rate >= 1.0
                )

                integrity_clean = (
                    full_provenance_recovery
                    and full_temporal_alignment
                    and fingerprint_mean_distance <= PHASH_MATCH_THRESHOLD
                    and duration_delta <= 0.25
                    and geometry_match
                )

                if integrity_clean:

                    tamper_assessment = (
                        "NO_MATERIAL_SOURCE_MISMATCH_DETECTED"
                    )

                elif (
                    recovery_rate >= 0.50
                    and fingerprint_match_rate >= 0.50
                ):

                    tamper_assessment = (
                        "LIKELY_PARTIAL_TEMPORAL_MODIFICATION"
                    )

                elif (
                    fingerprint_match_rate < 0.50
                    or fingerprint_mean_distance > 24
                ):

                    tamper_assessment = (
                        "LIKELY_MATERIAL_CONTENT_CHANGE"
                    )

                else:

                    tamper_assessment = (
                        "LIKELY_LOCAL_TEMPORAL_MODIFICATION"
                    )

                # ---------------------------------------------
                # Final authoritative response
                # ---------------------------------------------

                return {
                    "status": (
                        "verified"
                        if consistent
                        else "verified_with_inconsistency"
                    ),

                    # MIR consistency alone is not sufficient for AUTHENTIC.
                    # A valid provenance payload can survive inside a modified
                    # video, so AUTHENTIC requires the media-integrity gate too.
                    "verification": (
                        "AUTHENTIC"
                        if consistent and integrity_clean
                        else (
                            "PROVENANCE_INTEGRITY_MISMATCH"
                            if consistent
                            else "PROVENANCE_INCONSISTENT"
                        )
                    ),

                    "provenance_recovered":
                        True,

                    "source_match":
                        True,

                    "media_id":
                        dominant_media_id,

                    "model_name": (
                        reference_mir.get(
                            "model_name"
                        )
                        if reference_mir
                        else registry.get(
                            "model_name"
                        )
                    ),

                    "timestamp": (
                        reference_mir.get(
                            "timestamp"
                        )
                        if reference_mir
                        else registry.get(
                            "timestamp"
                        )
                    ),

                    "media_type":
                        "video",

                    "framework": (
                        reference_mir.get(
                            "framework",
                            "Aletheia",
                        )
                        if reference_mir
                        else "Aletheia"
                    ),

                    "mir_version": (
                        reference_mir.get(
                            "mir_version"
                        )
                        if reference_mir
                        else None
                    ),

                    # -----------------------------------------
                    # TRUE checkpoint recovery
                    # -----------------------------------------

                    "recovered_checkpoints":
                        checkpoint_probe[
                            "recovered_checkpoints"
                        ],

                    "checkpoint_count":
                        checkpoint_probe[
                            "checkpoint_count"
                        ],

                    "recovery_percentage":
                        checkpoint_probe[
                            "recovery_percentage"
                        ],

                    "checkpoint_results":
                        checkpoint_probe[
                            "checkpoint_results"
                        ],

                    # Total decoded frames is retained as
                    # diagnostic metadata only.
                    "scanned_frames":
                        len(frame_paths),

                    # -----------------------------------------
                    # Aligned pHash integrity
                    # -----------------------------------------

                    "fingerprint_match_rate":
                        fingerprint_score[
                            "match_rate"
                        ],

                    "fingerprint_matches":
                        fingerprint_score[
                            "matches"
                        ],

                    "fingerprint_checkpoints":
                        fingerprint_score[
                            "checkpoint_results"
                        ],

                    "fingerprint_mean_distance":
                        fingerprint_score[
                            "mean_distance"
                        ],

                    "tamper_windows":
                        _tamper_windows(
                            fingerprint_score[
                                "checkpoint_results"
                            ]
                        ),

                    "tamper_assessment":
                        tamper_assessment,

                    # -----------------------------------------
                    # Source/video metadata
                    # -----------------------------------------

                    "duration_delta_seconds":
                        round(
                            duration_delta,
                            3,
                        ),

                    "current_duration_seconds":
                        round(
                            info.duration,
                            3,
                        ),

                    "registered_duration_seconds":
                        round(
                            float(
                                registry.get(
                                    "duration",
                                    0.0,
                                )
                            ),
                            3,
                        ),

                    "geometry_match":
                        geometry_match,

                    "embedding_strategy":
                        registry.get(
                            "embedding_strategy",
                            "temporal_dct_polarity_v1",
                        ),

                    "observation": (
                        "Temporal provenance was recovered at "
                        "deterministic checkpoints and matched the "
                        "registered source. Media integrity is considered "
                        "clean only when all deterministic checkpoints and "
                        "all aligned temporal fingerprints match the "
                        "registered artifact."
                    ),
                }

            # =================================================
            # PAYLOAD RECOVERED BUT SOURCE NOT REGISTERED
            # =================================================

            return {
                "status":
                    "unregistered",

                "verification":
                    "PROVENANCE_RECOVERED_UNREGISTERED_SOURCE",

                "provenance_recovered":
                    True,

                "source_match":
                    False,

                "media_id":
                    dominant_media_id,

                "model_name": (
                    reference_mir.get(
                        "model_name"
                    )
                    if reference_mir
                    else None
                ),

                "timestamp": (
                    reference_mir.get(
                        "timestamp"
                    )
                    if reference_mir
                    else None
                ),

                "media_type":
                    "video",

                "framework":
                    "Aletheia",

                "recovered_checkpoints":
                    checkpoint_probe[
                        "recovered_checkpoints"
                    ],

                "checkpoint_count":
                    checkpoint_probe[
                        "checkpoint_count"
                    ],

                "recovery_percentage":
                    checkpoint_probe[
                        "recovery_percentage"
                    ],

                "checkpoint_results":
                    checkpoint_probe[
                        "checkpoint_results"
                    ],

                "scanned_frames":
                    len(frame_paths),

                "tamper_assessment":
                    "PROVENANCE_RECOVERED_UNREGISTERED_SOURCE",

                "observation": (
                    "A temporal provenance payload was "
                    "recovered, but its media_id is not "
                    "present in the registration database."
                ),
            }

        # ====================================================
        # STEP 4
        # Broad provenance discovery fallback.
        #
        # Used when exact deterministic checkpoints do not
        # recover provenance, e.g. after temporal shifts.
        # ====================================================

        discovery = await _discover_provenance(
            video_file_path,
            info,
        )

        if discovery:

            media_id = discovery[
                "media_id"
            ]

            registry = await db[
                "registered_videos"
            ].find_one({
                "video_id":
                    media_id
            })

            group = discovery[
                "group"
            ]

            representative_mir = (
                group[0]["mir"]
                if group
                else None
            )

            if registry:

                # We found the provenance outside the expected
                # checkpoint locations.
                #
                # This supports source identification but does
                # NOT allow us to claim checkpoint integrity.

                return {
                    "status":
                        "verified",

                    "verification":
                        "SOURCE_IDENTIFIED_BY_TEMPORAL_PROVENANCE",

                    "provenance_recovered":
                        True,

                    "source_match":
                        True,

                    "media_id":
                        media_id,

                    "model_name": (
                        representative_mir.get(
                            "model_name"
                        )
                        if representative_mir
                        else registry.get(
                            "model_name"
                        )
                    ),

                    "timestamp": (
                        representative_mir.get(
                            "timestamp"
                        )
                        if representative_mir
                        else registry.get(
                            "timestamp"
                        )
                    ),

                    "media_type":
                        "video",

                    "framework":
                        "Aletheia",

                    "recovered_checkpoints":
                        0,

                    "checkpoint_count":
                        len(
                            CHECKPOINT_FRACTIONS
                        ),

                    "recovery_percentage":
                        0.0,

                    "checkpoint_results":
                        [],

                    "scanned_frames":
                        len(
                            discovery[
                                "paths"
                            ]
                        ),

                    "tamper_assessment":
                        "INTEGRITY_REQUIRES_TEMPORAL_ALIGNMENT",

                    "observation": (
                        "Embedded provenance identity was "
                        "discovered outside the deterministic "
                        "checkpoint positions. This supports "
                        "source identification, but does not "
                        "by itself establish temporal integrity."
                    ),
                }

            return {
                "status":
                    "unregistered",

                "verification":
                    "PROVENANCE_RECOVERED_UNREGISTERED_SOURCE",

                "provenance_recovered":
                    True,

                "source_match":
                    False,

                "media_id":
                    media_id,

                "model_name": (
                    representative_mir.get(
                        "model_name"
                    )
                    if representative_mir
                    else None
                ),

                "timestamp": (
                    representative_mir.get(
                        "timestamp"
                    )
                    if representative_mir
                    else None
                ),

                "media_type":
                    "video",

                "framework":
                    "Aletheia",

                "recovered_checkpoints":
                    0,

                "checkpoint_count":
                    len(
                        CHECKPOINT_FRACTIONS
                    ),

                "recovery_percentage":
                    0.0,

                "checkpoint_results":
                    [],

                "scanned_frames":
                    len(
                        discovery[
                            "paths"
                        ]
                    ),

                "tamper_assessment":
                    "PROVENANCE_RECOVERED_UNREGISTERED_SOURCE",

                "observation": (
                    "A provenance payload was found, "
                    "but the referenced source is not registered."
                ),
            }

        # ====================================================
        # STEP 5
        # Final pHash-only source identification fallback.
        #
        # This is deliberately NOT labelled AUTHENTIC.
        # ====================================================

        scan_count = min(
            48,
            max(
                20,
                int(
                    info.duration * 10
                ),
            ),
        )

        times = [
            info.duration
            * (index + 0.5)
            / scan_count
            for index in range(
                scan_count
            )
        ]

        fallback_dir = tempfile.mkdtemp(
            prefix="aletheia_video_phash_"
        )

        try:

            paths = _extract_selected_frames(
                video_file_path,
                fallback_dir,
                times,
            )

            current_hashes = []

            for path in paths:

                try:

                    with Image.open(
                        path
                    ) as image:

                        current_hash = (
                            _frame_phash(
                                image
                            )
                        )

                    if current_hash:

                        current_hashes.append(
                            current_hash
                        )

                except Exception:

                    continue

            best = None

            cursor = db[
                "registered_videos"
            ].find({})

            async for registered_doc in cursor:

                references = [
                    item.get(
                        "phash"
                    )
                    for item in registered_doc.get(
                        "temporal_fingerprints",
                        [],
                    )
                    if item.get(
                        "phash"
                    )
                ]

                score = (
                    _temporal_fingerprint_score(
                        current_hashes,
                        references,
                    )
                )

                if (
                    score["matches"]
                    >= max(
                        4,
                        int(
                            0.25
                            * max(
                                1,
                                len(
                                    current_hashes
                                ),
                            )
                        ),
                    )
                    and score[
                        "mean_distance"
                    ] <= 16
                ):

                    if (
                        best is None
                        or (
                            score[
                                "match_rate"
                            ],
                            -score[
                                "mean_distance"
                            ],
                        )
                        > (
                            best[
                                "score"
                            ][
                                "match_rate"
                            ],
                            -best[
                                "score"
                            ][
                                "mean_distance"
                            ],
                        )
                    ):

                        best = {
                            "doc":
                                registered_doc,
                            "score":
                                score,
                        }

            if best:

                document = best[
                    "doc"
                ]

                score = best[
                    "score"
                ]

                return {
                    "status":
                        "verified",

                    "verification":
                        "SOURCE_IDENTIFIED_BY_TEMPORAL_FINGERPRINT",

                    "provenance_recovered":
                        False,

                    "source_match":
                        True,

                    "media_id":
                        document[
                            "video_id"
                        ],

                    "model_name":
                        document.get(
                            "model_name"
                        ),

                    "timestamp":
                        document.get(
                            "timestamp"
                        ),

                    "media_type":
                        "video",

                    "framework":
                        "Aletheia",

                    "recovered_checkpoints":
                        0,

                    "checkpoint_count":
                        len(
                            CHECKPOINT_FRACTIONS
                        ),

                    "recovery_percentage":
                        0.0,

                    "checkpoint_results":
                        [],

                    "scanned_frames":
                        score[
                            "total"
                        ],

                    "fingerprint_match_rate":
                        score[
                            "match_rate"
                        ],

                    "fingerprint_mean_distance":
                        score[
                            "mean_distance"
                        ],

                    "tamper_assessment":
                        "INTEGRITY_REQUIRES_TEMPORAL_ALIGNMENT",

                    "observation": (
                        "The temporal perceptual fingerprint "
                        "identified a registered source, but "
                        "embedded provenance was not recovered. "
                        "Source identification is not proof that "
                        "the current video is unmodified."
                    ),
                }

            return {
                "status":
                    "unavailable",

                "verification":
                    "PROVENANCE_NOT_RECOVERED",

                "provenance_recovered":
                    False,

                "source_match":
                    False,

                "recovered_checkpoints":
                    0,

                "checkpoint_count":
                    len(
                        CHECKPOINT_FRACTIONS
                    ),

                "recovery_percentage":
                    0.0,

                "checkpoint_results":
                    [],

                "scanned_frames":
                    len(paths),

                "tamper_assessment":
                    "PROVENANCE_NOT_RECOVERED",

                "observation": (
                    "No recoverable Aletheia temporal "
                    "provenance signal was found. This does "
                    "not prove that the video is non-AI."
                ),
            }

        finally:

            shutil.rmtree(
                fallback_dir,
                ignore_errors=True,
            )

    finally:

        shutil.rmtree(
            work,
            ignore_errors=True,
        )