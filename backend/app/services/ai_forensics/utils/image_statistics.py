"""
utils/image_statistics.py — Handcrafted statistical feature extraction.

Provides low-level feature functions used by the StatisticalDetector.
Each function is independently testable and documented.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def compute_entropy(image: Image.Image) -> float:
    """
    Compute Shannon entropy of the grayscale histogram.
    AI-generated images typically show unusual entropy profiles —
    either artificially uniform or with sharp histogram spikes.

    Returns: entropy in nats.
    """
    gray = np.array(image.convert("L"), dtype=np.uint8)
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    prob = hist / hist.sum()
    # Avoid log(0) by masking zero bins
    nonzero = prob[prob > 0]
    return float(-np.sum(nonzero * np.log(nonzero)))


def compute_rgb_histogram_stats(image: Image.Image) -> dict[str, float]:
    """
    Compute per-channel mean, standard deviation, and skewness.
    AI generators often produce unnaturally symmetric or shifted distributions.

    Returns a flat dict: {r_mean, r_std, r_skew, g_mean, ...}
    """
    arr = np.array(image, dtype=np.float32)
    stats = {}
    for idx, channel in enumerate(["r", "g", "b"]):
        ch = arr[:, :, idx].flatten()
        mean = float(ch.mean())
        std  = float(ch.std())
        n    = len(ch)
        skew = float(
            np.sum(((ch - mean) ** 3)) / (n * (std ** 3) + 1e-8)
        )
        stats[f"{channel}_mean"] = mean
        stats[f"{channel}_std"]  = std
        stats[f"{channel}_skew"] = skew
    return stats


def compute_edge_density(image: Image.Image) -> float:
    """
    Compute edge density using a Sobel-style Canny approximation via PIL.
    AI-generated images can exhibit either unnaturally sharp or unnaturally
    smooth edges depending on the generator.

    Returns: ratio of edge pixels to total pixels in [0, 1].
    """
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    arr = np.array(edges, dtype=np.float32)
    # Threshold at 10% of max response
    threshold = 0.1 * 255.0
    edge_ratio = float((arr > threshold).sum() / arr.size)
    return edge_ratio


def compute_laplacian_variance(image: Image.Image) -> float:
    """
    Compute the variance of the Laplacian of the grayscale image.
    Measures focus/sharpness. AI images often have unusual sharpness profiles —
    hyper-sharp in semantic regions, soft in backgrounds.

    Returns: Laplacian variance (higher = sharper).
    """
    gray = np.array(image.convert("L"), dtype=np.float32)
    # Manual 3x3 Laplacian kernel convolution
    from scipy.ndimage import laplace
    lap = laplace(gray)
    return float(lap.var())


def compute_noise_variance(image: Image.Image) -> float:
    """
    Estimate high-frequency noise variance by comparing the image against
    its own Gaussian-blurred version. Real camera images contain structured
    sensor noise; AI images often contain either no noise or unnaturally
    patterned noise.

    Returns: noise variance in [0, ∞).
    """
    arr   = np.array(image.convert("L"), dtype=np.float32)
    blur  = np.array(image.convert("L").filter(ImageFilter.GaussianBlur(radius=1)),
                     dtype=np.float32)
    noise = arr - blur
    return float(noise.var())
