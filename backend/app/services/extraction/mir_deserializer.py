"""
mir_deserializer.py — Reconstructs a MediaIdentityRecord from raw bytes.

Exact inverse of mir_serializer.serialize() in the embedding package.

The wire format is compact UTF-8 JSON with sorted keys and no whitespace,
as produced by json.dumps(..., sort_keys=True, separators=(",", ":")):

    {"framework":"Aletheia","media_id":"...","media_type":"image",
     "mir_version":"1.0","model_name":"...","timestamp":"..."}

This module imports MediaIdentityRecord from the embedding package.
That import is intentional: both packages share one canonical MIR type
so deserialized records are first-class objects usable anywhere.

Sprint 4 note:
    If the MIR schema is versioned (mir_version != "1.0"), add a
    dispatch table here to call the correct deserialization path
    without changing the extraction service.
"""

from __future__ import annotations

import json

from app.services.embedding.mir_serializer import MediaIdentityRecord
from app.services.extraction.bitstream_reader import ExtractionError

# Required MIR v1.0 fields — used for schema validation.
_REQUIRED_FIELDS = {
    "mir_version",
    "media_id",
    "model_name",
    "timestamp",
    "media_type",
    "framework",
}

_SUPPORTED_MIR_VERSIONS = {"1.0"}
_SUPPORTED_FRAMEWORKS   = {"Aletheia"}


def deserialize(data: bytes) -> MediaIdentityRecord:
    """
    Parse raw UTF-8 JSON bytes into a MediaIdentityRecord.

    Args:
        data: UTF-8 encoded JSON bytes as embedded by mir_serializer.serialize().

    Returns:
        MediaIdentityRecord — fully populated MIR.

    Raises:
        ExtractionError: If the bytes cannot be decoded as UTF-8, parsed as
                         JSON, do not contain all required fields, or declare
                         an unsupported framework / MIR version.
    """
    # ------------------------------------------------------------------
    # 1. Decode UTF-8
    # ------------------------------------------------------------------
    try:
        json_str = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            f"Payload is not valid UTF-8: {exc}. "
            "The image may not contain Aletheia provenance data."
        ) from exc

    # ------------------------------------------------------------------
    # 2. Parse JSON
    # ------------------------------------------------------------------
    try:
        d = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            f"Payload is not valid JSON: {exc}. "
            "The image may not contain Aletheia provenance data."
        ) from exc

    # ------------------------------------------------------------------
    # 3. Schema validation
    # ------------------------------------------------------------------
    missing = _REQUIRED_FIELDS - d.keys()
    if missing:
        raise ExtractionError(
            f"Recovered MIR is missing required fields: {sorted(missing)}."
        )

    if d["framework"] not in _SUPPORTED_FRAMEWORKS:
        raise ExtractionError(
            f"Unknown framework '{d['framework']}'. "
            f"Supported: {sorted(_SUPPORTED_FRAMEWORKS)}."
        )

    if d["mir_version"] not in _SUPPORTED_MIR_VERSIONS:
        raise ExtractionError(
            f"Unsupported MIR version '{d['mir_version']}'. "
            f"Supported: {sorted(_SUPPORTED_MIR_VERSIONS)}."
        )

    # ------------------------------------------------------------------
    # 4. Construct and return MIR
    # ------------------------------------------------------------------
    return MediaIdentityRecord(
        mir_version=d["mir_version"],
        media_id=d["media_id"],
        model_name=d["model_name"],
        timestamp=d["timestamp"],
        media_type=d["media_type"],
        framework=d["framework"],
    )
