"""Deterministic regional layout used by the production DCT provenance codec."""
from __future__ import annotations
from dataclasses import dataclass
from PIL import Image

@dataclass(frozen=True)
class DCTRegion:
    x: int
    y: int
    width: int
    height: int
    row: int
    col: int


def regions_for(image: Image.Image) -> list[DCTRegion]:
    w, h = image.size
    shortest = min(w, h)
    if shortest >= 512:
        rows = cols = 4
    elif shortest >= 256:
        rows = cols = 2
    else:
        rows = cols = 1
    bw, bh = w // cols, h // rows
    out = []
    for r in range(rows):
        for c in range(cols):
            x, y = c * bw, r * bh
            rw = w - x if c == cols - 1 else bw
            rh = h - y if r == rows - 1 else bh
            out.append(DCTRegion(x, y, rw, rh, r, c))
    return out
