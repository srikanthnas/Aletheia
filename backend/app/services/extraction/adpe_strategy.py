"""
adpe_strategy.py — Adaptive Distributed Provenance Embedding (ADPE) strategy.

Implements EmbeddingStrategy using the RegionManager + PayloadAllocator
infrastructure introduced in Sprint 3.

Architecture:
    ADPEStrategy is the second concrete EmbeddingStrategy in the Aletheia
    framework. It is the spiritual successor to LSBStrategy:

        LSBStrategy (Sprint 2)   -- sequential LSB across the full image.
        ADPEStrategy (Sprint 3+) -- region-aware, payload-distributed embedding.

Sprint 3 behaviour (v1 -- "primary-region mode"):
    1. RegionManager partitions the image into an adaptive grid.
    2. The primary region's channel_capacity is used as the size constraint.
    3. The bitstream is embedded sequentially into the full carrier starting
       at channel offset 0 (same as LSBStrategy). This is geometrically
       equivalent to writing into the primary region because the primary
       region always starts at (x=0, y=0) and the extraction pipeline reads
       the full image sequentially from channel 0.

    Result: identical output to LSBStrategy for Sprint 3, but the full ADPE
    infrastructure (RegionManager, PayloadAllocator) is active and ready for
    Sprint 4 to enable true multi-region distribution.

Sprint 4 upgrade path:
    For each additional region, compute:
        offset = (region.y * image_width + region.x) * 3
    Write that segment's bitstream at flat[offset]. The extraction service
    then calls read_raw_lsbs(image, n_bits, offset=offset) per region.
    No other modules need changing -- only this file and the extraction
    service's multi-region recovery loop.
"""

from __future__ import annotations

from PIL import Image

from app.services.embedding.embedding_strategy import EmbeddingStrategy
from app.services.extraction.region_manager import RegionManager, ImageRegion
from app.services.extraction.payload_allocator import PayloadAllocator


class ADPEStrategy(EmbeddingStrategy):
    """
    Adaptive Distributed Provenance Embedding strategy.

    Accepts optional RegionManager and PayloadAllocator at construction time,
    enabling full dependency injection for testing and future variants.

    Example (Sprint 3 -- use defaults):
        strategy = ADPEStrategy()
        embedded = strategy.embed(image, bitstream)

    Example (Sprint 4 -- inject custom components):
        strategy = ADPEStrategy(
            region_manager=ContentAwareRegionManager(),
            payload_allocator=ShardingAllocator(n_shards=4),
        )
    """

    STRATEGY_NAME = "adpe_v2_distributed"
    """
    Identifies the ADPE variant in stored metadata and API responses.
    Bumped to 'adpe_v2_distributed' for Sprint 5 multi-region embedding.
    """

    def __init__(
        self,
        region_manager: RegionManager | None = None,
        payload_allocator: PayloadAllocator | None = None,
    ) -> None:
        self._region_manager    = region_manager    or RegionManager()
        self._payload_allocator = payload_allocator or PayloadAllocator()

    # ------------------------------------------------------------------
    # EmbeddingStrategy interface
    # ------------------------------------------------------------------

    def embed(self, image: Image.Image, bitstream: list[int]) -> Image.Image:
        """
        Embed a bitstream into the image using ADPE.

        Sprint 3: embeds sequentially into the full carrier starting at
        channel offset 0, constrained by the primary region's capacity.
        This keeps the extraction pipeline (which reads channels sequentially
        from index 0) fully compatible.

        Args:
            image:     Source PIL Image (any mode; converted to RGB internally).
            bitstream: Flat list of 0/1 integers (header + payload bits).

        Returns:
            A new PIL Image with provenance embedded.

        Raises:
            ValueError: If the primary region has insufficient capacity.
        """
        carrier = image.copy().convert("RGB")

        # 1. Partition image and get primary region for capacity constraint
        regions = self._region_manager.partition(carrier)
        primary = self._region_manager.select_primary_region(regions)

        if len(bitstream) > primary.channel_capacity:
            raise ValueError(
                f"ADPE primary region ({primary.width}x{primary.height} px, "
                f"{primary.channel_capacity} bits) cannot hold the payload "
                f"({len(bitstream)} bits). Use a larger image."
            )

        # 2. Embed sequentially into the full carrier's flat channel array
        #    for EVERY region (Sprint 5 Multi-Region Embedding).
        pixels = list(carrier.getdata())
        flat: list[int] = []
        for r, g, b in pixels:
            flat.append(r)
            flat.append(g)
            flat.append(b)

        w, h = carrier.size
        for region in regions:
            offset = (region.y * w + region.x) * 3
            if region.channel_capacity < len(bitstream):
                continue
            
            row_capacity = region.width * 3
            for idx, bit in enumerate(bitstream):
                row = idx // row_capacity
                col = idx % row_capacity
                actual_offset = offset + (row * w * 3) + col
                if actual_offset < len(flat):
                    flat[actual_offset] = (flat[actual_offset] & 0xFE) | bit

        new_pixels = [
            (flat[i], flat[i + 1], flat[i + 2])
            for i in range(0, len(flat), 3)
        ]
        carrier.putdata(new_pixels)

        return carrier

    def capacity(self, image: Image.Image) -> int:
        """
        Return the embeddable bit capacity of the primary region.

        Unlike LSBStrategy which returns the full image capacity, ADPE
        reports only the primary region's capacity. Sprint 4 distributed
        mode will sum capacities across all selected regions.
        """
        regions = self._region_manager.partition(image)
        primary = self._region_manager.select_primary_region(regions)
        return primary.channel_capacity

    # ------------------------------------------------------------------
    # Inspection helpers (used by extraction service and future analytics)
    # ------------------------------------------------------------------

    def get_regions(self, image: Image.Image) -> list[ImageRegion]:
        """Return the full region partition for a given image."""
        return self._region_manager.partition(image)

    def get_primary_region(self, image: Image.Image) -> ImageRegion:
        """Return the primary embedding region for a given image."""
        return self._region_manager.select_primary_region(
            self._region_manager.partition(image)
        )
