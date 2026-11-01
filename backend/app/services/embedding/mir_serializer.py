"""
mir_serializer.py — Media Identity Record serialisation.

Converts a MIR dict into a deterministic UTF-8 byte payload
that is ready for binary encoding and embedding.

MIR structure (v1.0):
    {
        "mir_version": "1.0",
        "media_id":    "<UUID from Sprint 1>",
        "model_name":  "<AI model>",
        "timestamp":   "<ISO-8601 UTC>",
        "media_type":  "image",
        "framework":   "Aletheia"
    }
"""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MediaIdentityRecord:
    """
    Typed representation of a MIR.
    Kept as a dataclass so it is easy to extend in future sprints
    without breaking the serialiser interface.
    """

    mir_version: str
    media_id: str
    model_name: str
    timestamp: str
    media_type: str
    framework: str

    def to_dict(self) -> dict:
        return {
            "mir_version": self.mir_version,
            "media_id":    self.media_id,
            "model_name":  self.model_name,
            "timestamp":   self.timestamp,
            "media_type":  self.media_type,
            "framework":   self.framework,
        }


def build_mir(
    media_id: str,
    model_name: str,
    timestamp: str,
    media_type: str = "image",
    mir_version: str = "1.0",
    framework: str = "Aletheia",
) -> MediaIdentityRecord:
    """Factory that constructs a MIR from registered-media fields."""
    return MediaIdentityRecord(
        mir_version=mir_version,
        media_id=media_id,
        model_name=model_name,
        timestamp=timestamp,
        media_type=media_type,
        framework=framework,
    )


def serialize(mir: MediaIdentityRecord) -> bytes:
    """
    Serialize a MIR to a compact, deterministic UTF-8 JSON byte string.

    Uses sort_keys=True and no extra whitespace so the byte representation
    is identical for the same MIR regardless of insertion order.

    Returns:
        bytes — UTF-8 encoded JSON payload ready for binary encoding.
    """
    payload = json.dumps(mir.to_dict(), sort_keys=True, separators=(",", ":"))
    return payload.encode("utf-8")
