"""
lsb_strategy.py — Sequential Least Significant Bit (LSB) embedding strategy.

Implements EmbeddingStrategy for Sprint 2.

Algorithm:
    For each bit in the bitstream (including the 32-bit length header):
      - Take the next available pixel channel value (R, G, or B, in row-major order).
      - Clear its LSB and replace it with the target bit.
      - Continue until all bits are embedded.

Visual impact:
    Each pixel channel value changes by at most ±1 (e.g., 200 → 201 or 199).
    This delta is imperceptible to the human visual system, satisfying the
    "visually indistinguishable" requirement.

Capacity:
    max_bits = width × height × 3  (one bit per RGB channel)

Output format:
    Always saved as PNG (lossless) to prevent bit corruption from JPEG compression.

Future extensibility:
    Sprint 3 can introduce AdaptiveDistributedProvenanceEmbedding (ADPE) by
    creating adpe_strategy.py that subclasses EmbeddingStrategy.
    No changes required here or in any other module.
"""

from PIL import Image

from app.services.embedding.embedding_strategy import EmbeddingStrategy


class LSBStrategy(EmbeddingStrategy):
    """
    Sequential LSB steganography strategy.

    Embeds bits sequentially across all RGB channels of the image
    in row-major (left-to-right, top-to-bottom) order.
    """

    def embed(self, image: Image.Image, bitstream: list[int]) -> Image.Image:
        """
        Embed bitstream into a copy of the image using sequential LSB.

        Args:
            image:     Source PIL Image. Must be convertible to RGB.
            bitstream: Flat list of 0/1 integers (includes length header).

        Returns:
            A new PIL Image (RGB, PNG-compatible) with bits embedded in LSBs.

        Raises:
            ValueError: If the payload is larger than the image can hold.
        """
        # Work on a copy — never mutate the original
        carrier = image.copy().convert("RGB")

        total_bits = len(bitstream)
        max_bits = self.capacity(carrier)

        if total_bits > max_bits:
            raise ValueError(
                f"Payload too large: {total_bits} bits required, "
                f"but image capacity is only {max_bits} bits "
                f"({max_bits // 8} bytes). Use a larger image."
            )

        # Flatten all pixel channel values into a mutable list
        pixels = list(carrier.getdata())          # list of (R, G, B) tuples
        flat: list[int] = []
        for r, g, b in pixels:
            flat.append(r)
            flat.append(g)
            flat.append(b)

        # Sequential LSB replacement
        for idx, bit in enumerate(bitstream):
            flat[idx] = (flat[idx] & 0xFE) | bit  # clear LSB, set to bit

        # Reconstruct pixel tuples and write back to image
        new_pixels = [
            (flat[i], flat[i + 1], flat[i + 2])
            for i in range(0, len(flat), 3)
        ]
        carrier.putdata(new_pixels)

        return carrier

    def capacity(self, image: Image.Image) -> int:
        """Return the maximum embeddable bits for this image (RGB channels)."""
        w, h = image.size
        return w * h * 3
