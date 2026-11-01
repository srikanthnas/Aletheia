"""
app/services/extraction/__init__.py

Public surface of the extraction sub-package.

Sprint 4 can import from here without knowing internal module names.
"""

from app.services.extraction.bitstream_reader import (
    ExtractionError,
    read_raw_lsbs,
    read_payload_bitstream,
)
from app.services.extraction.binary_decoder import (
    bits_to_bytes,
    decode_full_bitstream,
)
from app.services.extraction.mir_deserializer import deserialize
from app.services.extraction.region_manager import RegionManager, ImageRegion
from app.services.extraction.payload_allocator import PayloadAllocator, PayloadSegment
from app.services.extraction.adpe_strategy import ADPEStrategy

__all__ = [
    # Error
    "ExtractionError",
    # Bitstream reading
    "read_raw_lsbs",
    "read_payload_bitstream",
    # Decoding
    "bits_to_bytes",
    "decode_full_bitstream",
    # MIR
    "deserialize",
    # ADPE infrastructure
    "RegionManager",
    "ImageRegion",
    "PayloadAllocator",
    "PayloadSegment",
    "ADPEStrategy",
]
