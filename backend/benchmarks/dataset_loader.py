"""
dataset_loader.py — Dataset abstractions for the AI Forensics benchmarking framework.

Architecture
------------
The dataset layer follows an abstract base class pattern (Dataset protocol)
so that new dataset sources can be added without touching the BenchmarkRunner.

Provided implementations:
  - DirectoryDataset : Loads labeled images from two directories (real/ and fake/).
  - SyntheticDataset : Generates synthetic test images without requiring a real dataset.
                       Synthetic images are not realistic but allow the framework to
                       be tested without external data.

Label Convention
----------------
  label=0  →  Real / authentic / camera photograph
  label=1  →  AI-generated / synthetic / fake

This matches the DetectionResult.score convention:
  score ≈ 0.0  →  authentic
  score ≈ 1.0  →  AI-generated
"""
from __future__ import annotations

import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Labeled sample type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LabeledSample:
    """
    A single evaluation sample.

    Fields
    ------
    image      : PIL Image (RGB mode) ready for detector.analyze().
    label      : Ground truth. 0 = real, 1 = AI-generated.
    source_path: File path or description of image origin.
    """
    image: Image.Image
    label: int          # 0 = real, 1 = AI-generated
    source_path: str

    def __post_init__(self) -> None:
        if self.label not in (0, 1):
            raise ValueError(f"label must be 0 or 1, got {self.label}")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Dataset(ABC):
    """
    Abstract base class for benchmark datasets.

    Subclasses must implement __iter__ and __len__ to produce
    LabeledSample objects. The BenchmarkRunner depends only on this interface.
    """

    @abstractmethod
    def __iter__(self) -> Iterator[LabeledSample]:
        """Yield LabeledSample objects one by one."""
        ...

    @abstractmethod
    def __len__(self) -> int:
        """Return the total number of samples."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of this dataset."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Directory dataset (real labeled data)
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp",
})


class DirectoryDataset(Dataset):
    """
    Loads labeled images from two directories.

    Expected structure::

        real_dir/    ← Images labeled 0 (authentic)
            photo_001.jpg
            photo_002.png
            ...

        fake_dir/    ← Images labeled 1 (AI-generated)
            ai_001.png
            midjourney_001.jpg
            ...

    Images are loaded lazily when iterated.

    Args:
        real_dir : Path to the directory of authentic images.
        fake_dir : Path to the directory of AI-generated images.
        max_samples : Optional limit on total samples (balanced across classes).
        shuffle     : Randomize iteration order (default True).
        seed        : Random seed for reproducible shuffling.
    """

    def __init__(
        self,
        real_dir: str | Path,
        fake_dir: str | Path,
        max_samples: int | None = None,
        shuffle: bool = True,
        seed: int = 42,
    ) -> None:
        real_dir = Path(real_dir)
        fake_dir = Path(fake_dir)

        if not real_dir.is_dir():
            raise ValueError(f"real_dir does not exist or is not a directory: {real_dir}")
        if not fake_dir.is_dir():
            raise ValueError(f"fake_dir does not exist or is not a directory: {fake_dir}")

        real_paths = self._collect_paths(real_dir)
        fake_paths = self._collect_paths(fake_dir)

        if not real_paths:
            raise ValueError(f"No supported image files found in real_dir: {real_dir}")
        if not fake_paths:
            raise ValueError(f"No supported image files found in fake_dir: {fake_dir}")

        # Balance classes if max_samples is set
        if max_samples is not None:
            per_class = max_samples // 2
            real_paths = real_paths[:per_class]
            fake_paths = fake_paths[:per_class]

        self._samples: list[tuple[str, int]] = (
            [(p, 0) for p in real_paths]
            + [(p, 1) for p in fake_paths]
        )

        if shuffle:
            rng = random.Random(seed)
            rng.shuffle(self._samples)

        self._real_dir = real_dir
        self._fake_dir = fake_dir

    @staticmethod
    def _collect_paths(directory: Path) -> list[str]:
        """Return sorted list of image file paths in a directory."""
        paths = [
            str(p)
            for p in sorted(directory.iterdir())
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        return paths

    def __iter__(self) -> Iterator[LabeledSample]:
        for path, label in self._samples:
            try:
                image = Image.open(path).convert("RGB")
                yield LabeledSample(image=image, label=label, source_path=path)
            except Exception as exc:
                # Skip corrupted images; log the issue
                import logging
                logging.getLogger(__name__).warning(
                    "[DirectoryDataset] Skipping %s: %s", path, exc
                )

    def __len__(self) -> int:
        return len(self._samples)

    @property
    def name(self) -> str:
        return (
            f"DirectoryDataset("
            f"real={os.path.basename(self._real_dir)}, "
            f"fake={os.path.basename(self._fake_dir)}, "
            f"n={len(self._samples)})"
        )


# ---------------------------------------------------------------------------
# Synthetic dataset (no external data required)
# ---------------------------------------------------------------------------

class SyntheticDataset(Dataset):
    """
    Generates synthetic labeled images without requiring an external dataset.

    Useful for:
      - Testing the benchmarking framework when no labeled dataset is available.
      - Verifying that the pipeline runs end-to-end without errors.
      - Establishing baseline performance with known-trivial samples.

    WARNING: Synthetic images do not reflect real-world AI image characteristics.
    Benchmark results from synthetic data are NOT scientifically meaningful.
    Use only for framework validation.

    Synthetic image types:
      label=0 (real):  Natural noise texture (Gaussian noise over a grey canvas).
      label=1 (fake):  Uniform gradient (artificially clean, near-zero noise).

    These are designed to produce detectable statistical differences in the
    StatisticalDetector (noise variance) so that the pipeline can be tested.

    Args:
        n_real    : Number of synthetic 'real' images.
        n_fake    : Number of synthetic 'AI-generated' images.
        image_size: (width, height) of generated images.
        seed      : Random seed for reproducibility.
    """

    def __init__(
        self,
        n_real: int = 20,
        n_fake: int = 20,
        image_size: tuple[int, int] = (224, 224),
        seed: int = 42,
    ) -> None:
        if n_real < 1 or n_fake < 1:
            raise ValueError("n_real and n_fake must be at least 1.")
        self._n_real = n_real
        self._n_fake = n_fake
        self._size = image_size
        self._seed = seed

    def _generate_real(self, index: int) -> Image.Image:
        """
        Generate a synthetic 'real' image.
        Uses Gaussian noise to simulate natural photographic sensor noise.
        """
        rng = np.random.default_rng(self._seed + index)
        base = rng.integers(80, 180, size=(*self._size[::-1], 3), dtype=np.uint8)
        noise = rng.normal(0, 30, size=(*self._size[::-1], 3)).astype(np.int16)
        noisy = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(noisy, mode="RGB")

    def _generate_fake(self, index: int) -> Image.Image:
        """
        Generate a synthetic 'AI-generated' image.
        Uses a smooth gradient — artificially clean with near-zero noise.
        """
        rng = np.random.default_rng(self._seed + 1000 + index)
        w, h = self._size
        # Create smooth gradient
        x = np.linspace(0, 255, w, dtype=np.float32)
        y = np.linspace(0, 255, h, dtype=np.float32)
        xv, yv = np.meshgrid(x, y)
        # Random colour bias for each channel
        r_bias = rng.uniform(0.4, 0.8)
        g_bias = rng.uniform(0.2, 0.6)
        b_bias = rng.uniform(0.3, 0.7)
        arr = np.stack([
            (xv * r_bias).clip(0, 255),
            (yv * g_bias).clip(0, 255),
            ((xv + yv) / 2 * b_bias).clip(0, 255),
        ], axis=-1).astype(np.uint8)
        return Image.fromarray(arr, mode="RGB")

    def __iter__(self) -> Iterator[LabeledSample]:
        for i in range(self._n_real):
            yield LabeledSample(
                image=self._generate_real(i),
                label=0,
                source_path=f"synthetic://real/{i}",
            )
        for i in range(self._n_fake):
            yield LabeledSample(
                image=self._generate_fake(i),
                label=1,
                source_path=f"synthetic://fake/{i}",
            )

    def __len__(self) -> int:
        return self._n_real + self._n_fake

    @property
    def name(self) -> str:
        return f"SyntheticDataset(n_real={self._n_real}, n_fake={self._n_fake})"
