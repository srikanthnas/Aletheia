"""
payload_allocator.py — Distributes MIR payload segments across image regions.

Prepares the data layout for ADPE distributed embedding.

Sprint 3 behaviour:
    The allocator assigns the FULL payload to every region (full redundancy).
    This is architecturally correct and simplifies extraction: any single
    region can be read to recover the complete MIR.

Sprint 4 evolution:
    - Introduce segment-level checksums (CRC32 per region).
    - Split the payload into N shards (one per region) for space efficiency.
    - Add a Reed-Solomon / XOR parity shard for fault tolerance.
    - Override the allocation strategy by subclassing PayloadAllocator.

Usage:
    allocator = PayloadAllocator()
    segments  = allocator.allocate(payload_bytes, regions)
    for seg in segments:
        strategy.embed_region(image, seg.region, encode(seg.data))
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.services.extraction.region_manager import ImageRegion


@dataclass(frozen=True)
class PayloadSegment:
    """
    A unit of payload assigned to a specific image region.

    Attributes:
        region:   The ImageRegion this segment targets.
        data:     The raw bytes to embed in this region.
        checksum: SHA-256 hex digest of the data (for future integrity checks).
        index:    Segment index within the full allocation plan.
    """

    region: ImageRegion
    data: bytes
    checksum: str
    index: int

    @property
    def bit_count(self) -> int:
        """Number of bits required to embed this segment (header + payload)."""
        # 32 header bits + 8 bits per data byte
        return 32 + len(self.data) * 8

    def fits_in_region(self) -> bool:
        """Return True if this segment fits within the region's capacity."""
        return self.bit_count <= self.region.channel_capacity

    def __repr__(self) -> str:
        return (
            f"PayloadSegment(index={self.index}, region=({self.region.row},{self.region.col}), "
            f"data_bytes={len(self.data)}, fits={self.fits_in_region()})"
        )


class PayloadAllocator:
    """
    Assigns payload bytes to image regions for distributed embedding.

    Subclass and override allocate() to implement alternative strategies
    (sharding, erasure coding, parity, etc.) without changing ADPE or
    the extraction service.
    """

    def allocate(
        self,
        payload: bytes,
        regions: list[ImageRegion],
    ) -> list[PayloadSegment]:
        """
        Create a PayloadSegment for each region.

        Sprint 3: assigns the full payload to every region (broadcast mode).
        This guarantees that the MIR can be recovered from any single region,
        making the embedded provenance resilient to partial image cropping.

        Args:
            payload: The serialised MIR bytes to embed.
            regions: List of ImageRegion objects from RegionManager.partition().

        Returns:
            list[PayloadSegment] — one segment per region, in region order.
        """
        checksum = hashlib.sha256(payload).hexdigest()
        segments: list[PayloadSegment] = []

        for idx, region in enumerate(regions):
            segments.append(
                PayloadSegment(
                    region=region,
                    data=payload,
                    checksum=checksum,
                    index=idx,
                )
            )

        return segments

    def validate_capacity(
        self,
        segments: list[PayloadSegment],
    ) -> list[PayloadSegment]:
        """
        Return only segments whose payload fits within the target region.

        Useful for Sprint 4 sharding where different segment sizes may
        not fit in all regions equally.

        Args:
            segments: Output of allocate().

        Returns:
            Filtered list of PayloadSegment where fits_in_region() is True.
        """
        return [s for s in segments if s.fits_in_region()]
