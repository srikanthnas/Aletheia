"""
frequency/spectral_utils.py — Shared frequency-domain utilities.

Provides low-level mathematical operations for frequency analysis.
All functions are pure (no side effects) and independently testable.

Functions
---------
- compute_2d_fft           : 2D FFT with DC centering and log magnitude
- compute_radial_profile   : Radial averaging from 2D spectrum to 1D
- compute_block_boundary_ratio : JPEG block discontinuity analysis
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# FFT operations
# ---------------------------------------------------------------------------

def compute_2d_fft(gray: np.ndarray) -> np.ndarray:
    """
    Compute 2D FFT magnitude spectrum with DC component centered.

    Args:
        gray: Grayscale image array (H, W), dtype float32.

    Returns:
        Log-magnitude spectrum (H, W), DC component at center.
        Values are log(1 + |F|) to compress dynamic range.

    Notes:
        - Uses np.fft.fftshift to move DC component to center
        - Log scaling makes spectral patterns more visible
        - Adding 1 prevents log(0)
    """
    fft = np.fft.fft2(gray)
    fft_shifted = np.fft.fftshift(fft)
    magnitude = np.log(1.0 + np.abs(fft_shifted))
    return magnitude


def compute_radial_profile(spectrum: np.ndarray) -> np.ndarray:
    """
    Extract 1D radial average from 2D frequency spectrum.

    Converts a 2D magnitude spectrum into a 1D power profile by averaging
    all frequency components at the same radial distance from the DC center.

    Args:
        spectrum: 2D magnitude spectrum (H, W), DC component centered.

    Returns:
        1D array of radial-averaged power, indexed by distance from center.
        Length is approximately min(H, W) // 2.

    Algorithm:
        For each pixel (i, j):
          1. Compute distance r from center: r = sqrt((i-cy)^2 + (j-cx)^2)
          2. Round r to nearest integer bin
          3. Accumulate spectrum[i, j] into bin[r]
          4. Average each bin by its pixel count

    Notes:
        - Used for 1/f power law analysis
        - Real photos: smooth 1/f^α falloff
        - AI images: deviations from natural power law
    """
    h, w = spectrum.shape
    center_y, center_x = h // 2, w // 2

    # Create coordinate grids
    y, x = np.ogrid[:h, :w]
    r = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2).astype(int)

    # Radial binning
    max_radius = min(center_x, center_y)
    radial_profile = np.zeros(max_radius, dtype=np.float64)
    bin_count = np.zeros(max_radius, dtype=np.int32)

    for radius in range(max_radius):
        mask = (r == radius)
        if mask.any():
            radial_profile[radius] = spectrum[mask].mean()
            bin_count[radius] = mask.sum()

    # Avoid division by zero
    radial_profile[bin_count == 0] = 0.0

    return radial_profile


# ---------------------------------------------------------------------------
# DCT / JPEG compression analysis
# ---------------------------------------------------------------------------

def compute_block_boundary_ratio(gray: np.ndarray, block_size: int = 8) -> float:
    """
    Compute variance ratio: block boundaries vs. within blocks.

    Measures JPEG compression fingerprint by analyzing 8×8 block boundaries.
    Real JPEG images show higher variance at block boundaries due to
    quantization discontinuities. AI images (PNG exports) show smooth
    transitions across block boundaries.

    Args:
        gray: Grayscale image array (H, W), dtype float32.
        block_size: DCT block size (JPEG standard is 8).

    Returns:
        Ratio of boundary variance to within-block variance.
        Real JPEG photos: ratio > 1.5
        AI PNG exports:   ratio ≈ 1.0

    Algorithm:
        1. Partition image into non-overlapping 8×8 blocks
        2. Extract all horizontal and vertical block boundaries
        3. Compute variance across boundary pixels
        4. Compute variance within each block (excluding boundaries)
        5. Return ratio = boundary_var / within_var

    Notes:
        - JPEG quantization creates perceptible block boundaries
        - AI generators output PNG → no block artifacts
        - Strong signal for separating camera photos from AI exports
    """
    h, w = gray.shape

    # Ensure image dimensions are multiples of block_size
    h_blocks = h // block_size
    w_blocks = w // block_size

    if h_blocks < 2 or w_blocks < 2:
        # Image too small for meaningful block analysis
        return 1.0

    # Trim image to exact block grid
    gray = gray[: h_blocks * block_size, : w_blocks * block_size]

    # Extract boundary pixels
    boundary_pixels = []

    # Horizontal boundaries (between rows of blocks)
    for i in range(1, h_blocks):
        row_idx = i * block_size
        # Pixels just above boundary
        boundary_pixels.append(gray[row_idx - 1, :].flatten())
        # Pixels just below boundary
        boundary_pixels.append(gray[row_idx, :].flatten())

    # Vertical boundaries (between columns of blocks)
    for j in range(1, w_blocks):
        col_idx = j * block_size
        # Pixels just left of boundary
        boundary_pixels.append(gray[:, col_idx - 1].flatten())
        # Pixels just right of boundary
        boundary_pixels.append(gray[:, col_idx].flatten())

    boundary_pixels = np.concatenate(boundary_pixels)
    boundary_var = float(boundary_pixels.var())

    # Extract within-block pixels (excluding boundary rows/cols)
    within_pixels = []
    for i in range(h_blocks):
        for j in range(w_blocks):
            block = gray[
                i * block_size : (i + 1) * block_size,
                j * block_size : (j + 1) * block_size,
            ]
            # Exclude boundary pixels (first/last row/col of each block)
            interior = block[1:-1, 1:-1]
            if interior.size > 0:
                within_pixels.append(interior.flatten())

    if not within_pixels:
        # Blocks too small to have interior pixels
        return 1.0

    within_pixels = np.concatenate(within_pixels)
    within_var = float(within_pixels.var())

    # Avoid division by zero
    if within_var < 1e-8:
        return 1.0

    ratio = boundary_var / within_var
    return float(ratio)
