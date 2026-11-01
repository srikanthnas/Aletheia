"""
embedding_strategy.py — Abstract base class for all provenance embedding strategies.

Design intent (Open/Closed Principle):
  - This ABC defines the single contract: embed(image, bitstream) → Image
  - Sprint 2 uses LSBStrategy (sequential).
  - Sprint 3+ can introduce AdaptiveDistributedProvenanceEmbedding (ADPE)
    by subclassing EmbeddingStrategy and injecting it into
    ProvenanceEmbeddingService — no other module changes required.
"""

from abc import ABC, abstractmethod
from PIL import Image


class EmbeddingStrategy(ABC):
    """
    Abstract embedding strategy.

    All concrete strategies MUST implement `embed()`.
    The provenance embedding service depends ONLY on this interface,
    making the strategy fully swappable at runtime via dependency injection.
    """

    @abstractmethod
    def embed(self, image: Image.Image, bitstream: list[int]) -> Image.Image:
        """
        Embed a binary bitstream into the provided image.

        Args:
            image:     PIL Image object (source image, will not be mutated).
            bitstream: Flat list of integers (0 or 1) representing the
                       serialised MIR payload, including the 32-bit length
                       header prepended by binary_encoder.

        Returns:
            A new PIL Image with the bitstream embedded.
            The returned image MUST be visually indistinguishable from the
            original under normal viewing conditions.

        Raises:
            ValueError: If the image does not have sufficient capacity to
                        embed the entire bitstream.
        """
        ...

    def capacity(self, image: Image.Image) -> int:
        """
        Return the maximum number of bits this strategy can embed into
        the given image.  Subclasses should override for accurate reporting.
        Default implementation returns the flat RGB channel count.
        """
        w, h = image.size
        return w * h * 3
