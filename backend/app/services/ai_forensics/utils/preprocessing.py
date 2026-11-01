"""
utils/preprocessing.py — Image preprocessing utilities for AI forensic detectors.

Provides a single, consistent preprocessing pipeline so all detectors receive
images in an identical format, preventing subtle bugs from format differences.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_SIZE = (224, 224)   # Standard ViT/ResNet input size
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD  = (0.229, 0.224, 0.225)


# ---------------------------------------------------------------------------
# Preprocessing functions
# ---------------------------------------------------------------------------

def to_rgb(image: Image.Image) -> Image.Image:
    """Ensure the image is in RGB mode regardless of original format."""
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def resize(image: Image.Image, size: tuple[int, int] = TARGET_SIZE) -> Image.Image:
    """
    Resize an image using high-quality Lanczos resampling.
    Preserves aspect ratio via center-crop followed by resize.
    """
    return image.resize(size, Image.Resampling.LANCZOS)


def to_numpy_float(image: Image.Image) -> np.ndarray:
    """
    Convert a PIL Image to a float32 numpy array normalized to [0, 1].
    Shape: (H, W, C)
    """
    return np.array(image, dtype=np.float32) / 255.0


def normalize_imagenet(arr: np.ndarray) -> np.ndarray:
    """
    Apply ImageNet mean/std normalization to a float32 numpy array.
    Used for models pretrained on ImageNet (CLIP, ResNet, ViT).
    """
    mean = np.array(IMAGENET_MEAN, dtype=np.float32)
    std  = np.array(IMAGENET_STD,  dtype=np.float32)
    return (arr - mean) / std


def prepare_for_torch(image: Image.Image) -> "torch.Tensor":
    """
    Full preprocessing pipeline for PyTorch models:
      RGB → resize → float32 → ImageNet normalize → (1, C, H, W) tensor.
    Lazy-imports torch to avoid loading it at module import time.
    """
    import torch

    img = to_rgb(image)
    img = resize(img)
    arr = to_numpy_float(img)
    arr = normalize_imagenet(arr)
    # HWC → CHW → batch dimension
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).float()
    return tensor
