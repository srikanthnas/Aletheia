"""Supplementary, transformation-aware integrity features.

These are deliberately lightweight. They complement the claimed pHash and
steganographic provenance components rather than replacing them.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageOps


def dhash_hex(image: Image.Image, size: int = 8) -> str:
    gray = ImageOps.grayscale(image).resize((size + 1, size), Image.Resampling.LANCZOS)
    a = np.asarray(gray, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:0{size * size // 4}x}"


def hamming_hex(a: str, b: str) -> int:
    if len(a) != len(b):
        raise ValueError("Hash lengths differ")
    return sum((int(x, 16) ^ int(y, 16)).bit_count() for x, y in zip(a, b))


def hash_similarity(a: str, b: str) -> float:
    return max(0.0, 100.0 * (1.0 - hamming_hex(a, b) / (len(a) * 4)))


def _gray_array(image: Image.Image, size: tuple[int, int] = (512, 512)) -> np.ndarray:
    return np.asarray(ImageOps.grayscale(image).resize(size, Image.Resampling.BILINEAR), dtype=np.float32)


def histogram_distance(reference: Image.Image, current: Image.Image) -> float:
    a = _gray_array(reference)
    b = _gray_array(current)
    ha, _ = np.histogram(a, bins=32, range=(0, 255), density=True)
    hb, _ = np.histogram(b, bins=32, range=(0, 255), density=True)
    return float(np.sum(np.abs(ha - hb)) / (np.sum(ha + hb) + 1e-9))


def local_similarity(reference: Image.Image, current: Image.Image, grid: int = 4) -> tuple[float, float]:
    """Return (mean local similarity %, changed-region %).

    Images are normalized to the reference dimensions first. Each block is
    compared after removing its mean luminance, making brightness/contrast
    changes less likely to look like localized content edits.
    """
    ref = np.asarray(ImageOps.grayscale(reference), dtype=np.float32)
    cur_img = ImageOps.grayscale(current).resize(reference.size, Image.Resampling.BILINEAR)
    cur = np.asarray(cur_img, dtype=np.float32)
    h, w = ref.shape
    bh, bw = h // grid, w // grid
    sims = []
    changed = 0
    for r in range(grid):
        for c in range(grid):
            y0, y1 = r * bh, h if r == grid - 1 else (r + 1) * bh
            x0, x1 = c * bw, w if c == grid - 1 else (c + 1) * bw
            a = ref[y0:y1, x0:x1]
            b = cur[y0:y1, x0:x1]
            aa = a - float(a.mean())
            bb = b - float(b.mean())
            denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
            corr = float(np.sum(aa * bb) / denom) if denom > 1e-6 else 1.0
            sim = max(0.0, min(100.0, (corr + 1.0) * 50.0))
            sims.append(sim)
            if sim < 80.0:
                changed += 1
    return float(np.mean(sims)), float(100.0 * changed / len(sims))


def edge_density(image: Image.Image) -> float:
    arr = _gray_array(image)
    # Sobel-free gradient magnitude keeps this dependency-light.
    gx = np.diff(arr, axis=1)
    gy = np.diff(arr, axis=0)
    mag = np.sqrt(gx[:-1, :] ** 2 + gy[:, :-1] ** 2)
    return float(np.mean(mag > 24.0))


def high_frequency_energy(image: Image.Image) -> float:
    arr = _gray_array(image)
    blur = np.asarray(Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=2)), dtype=np.float32)
    residual = arr - blur
    return float(np.mean(residual ** 2))
