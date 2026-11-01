"""
region_manager.py — Adaptive image region partitioning for ADPE.

Partitions an image into a grid of non-overlapping rectangular regions
whose count and size are determined adaptively from image resolution.

Grid selection heuristic:
    │ Shortest dimension  │ Grid  │ Regions │ Min bits/region   │
    │────────────────────│───────│─────────│───────────────────│
    │ < 256 px            │ 1×1   │   1     │ all channels      │
    │ 256 – 511 px        │ 2×2   │   4     │ w·h·3 / 4         │
    │ 512 – 1023 px       │ 4×4   │  16     │ w·h·3 / 16        │
    │ ≥ 1024 px           │ 8×8   │  64     │ w·h·3 / 64        │

Design:
    RegionManager is consumed by:
      - ADPEStrategy.embed()  → determines WHICH regions to write into.
      - Sprint 4 extraction   → determines WHICH regions to read from.

Sprint 4 extension points:
    - Override select_primary_region() to implement deterministic or
      content-aware region selection (e.g. based on variance / DCT).
    - Override allocate_redundancy() to control how many regions
      receive a redundant copy of each payload segment.
"""

from __future__ import annotations

from dataclasses import dataclass
from PIL import Image


@dataclass(frozen=True)
class ImageRegion:
    """
    A rectangular crop of the carrier image.

    All coordinates are in pixels, measured from the top-left corner.
    """

    x: int          # Left edge (inclusive)
    y: int          # Top edge  (inclusive)
    width: int      # Region width  in pixels
    height: int     # Region height in pixels
    row: int        # Grid row index (0-based)
    col: int        # Grid column index (0-based)

    @property
    def channel_capacity(self) -> int:
        """Maximum bits embeddable in this region (3 channels per pixel)."""
        return self.width * self.height * 3

    def crop(self, image: Image.Image) -> Image.Image:
        """Return a cropped copy of the image for this region."""
        return image.crop((self.x, self.y, self.x + self.width, self.y + self.height))

    def __repr__(self) -> str:
        return (
            f"ImageRegion(row={self.row}, col={self.col}, "
            f"x={self.x}, y={self.y}, w={self.width}, h={self.height}, "
            f"capacity={self.channel_capacity} bits)"
        )


class RegionManager:
    """
    Adaptively partitions an image into a uniform grid based on resolution.

    Usage:
        manager = RegionManager()
        regions = manager.partition(image)          # list[ImageRegion]
        primary = manager.select_primary_region(regions)  # ImageRegion
    """

    # Thresholds for grid selection (based on shortest dimension)
    _GRID_THRESHOLDS = [
        (1024, (8, 8)),
        (512,  (4, 4)),
        (256,  (2, 2)),
        (0,    (1, 1)),
    ]

    def select_grid(self, image: Image.Image) -> tuple[int, int]:
        """
        Choose the (rows, cols) grid dimensions for the given image.

        Args:
            image: The carrier image.

        Returns:
            (rows, cols) tuple — e.g. (4, 4) for a 600×800 image.
        """
        shortest = min(image.size)
        for threshold, grid in self._GRID_THRESHOLDS:
            if shortest >= threshold:
                return grid
        return (1, 1)

    def partition(self, image: Image.Image) -> list[ImageRegion]:
        """
        Partition the image into a grid of non-overlapping ImageRegion objects.

        Remainder pixels (from integer division) are absorbed into the last
        row / column so the entire image area is covered.

        Args:
            image: The carrier image (mode will not be changed).

        Returns:
            list[ImageRegion] in row-major order (top-left → bottom-right).
        """
        w, h = image.size
        rows, cols = self.select_grid(image)

        base_rw = w // cols
        base_rh = h // rows

        regions: list[ImageRegion] = []
        for r in range(rows):
            for c in range(cols):
                x = c * base_rw
                y = r * base_rh
                # Last column/row absorbs remainder pixels
                rw = w - x if c == cols - 1 else base_rw
                rh = h - y if r == rows - 1 else base_rh
                regions.append(ImageRegion(x=x, y=y, width=rw, height=rh, row=r, col=c))

        return regions

    def select_primary_region(self, regions: list[ImageRegion]) -> ImageRegion:
        """
        Choose the primary embedding region.

        Sprint 3: always returns the first region (top-left).
        Sprint 4: can override to select based on DCT energy, variance, etc.

        Args:
            regions: List produced by partition().

        Returns:
            The chosen primary ImageRegion.
        """
        return regions[0]

    def select_redundant_regions(
        self,
        regions: list[ImageRegion],
        n: int = 0,
    ) -> list[ImageRegion]:
        """
        Choose regions for redundant payload copies.

        Sprint 3: returns an empty list (no redundancy yet).
        Sprint 4: returns `n` additional regions for fault-tolerant extraction.

        Args:
            regions: Full list of image regions.
            n:       Number of additional regions to use (default 0).

        Returns:
            list[ImageRegion] — additional embedding targets.
        """
        if n == 0 or len(regions) <= 1:
            return []
        # Skip primary (index 0), take evenly spaced extras
        step = max(1, (len(regions) - 1) // n)
        extras = regions[1::step]
        return extras[:n]
