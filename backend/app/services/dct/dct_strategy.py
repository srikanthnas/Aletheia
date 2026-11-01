"""Production DCT-QIM/RDM provenance embedding strategy.

The public DCT-QIM component remains unchanged conceptually.  Production
embedding can additionally use a distributed, error-corrected MIR: the same
signed/validated provenance frame is embedded independently in deterministic
image regions.  This makes localized edits damage only part of the provenance
rather than destroying the single global payload.
"""
from __future__ import annotations

from PIL import Image

from app.services.embedding.embedding_strategy import EmbeddingStrategy
from app.services.dct.block_processor import (
    get_ycbcr_channels,
    get_blocks_8x8,
    reconstruct_y_channel,
    reconstruct_image,
)
from app.services.dct.dct_transform import forward_dct_8x8, inverse_dct_8x8
from app.services.dct.coefficient_selector import get_embeddable_coefficients
from app.services.dct.qim_embedder import embed_bit, extract_bit
from app.services.dct.distributed_layout import regions_for


class DCTStrategy(EmbeddingStrategy):
    """DCT-QIM with optional distributed regional provenance embedding."""

    STRATEGY_NAME = "dct_qim"
    Q_STEP = 16.0
    ROBUST_STRATEGY_NAME = "dct_qim_rdm_distributed_v2"

    def __init__(self, distributed: bool = False) -> None:
        self.distributed = distributed

    def embed(self, image: Image.Image, bitstream: list[int]) -> Image.Image:
        if self.distributed:
            return self._embed_distributed(image, bitstream)
        return self._embed_single(image, bitstream)

    def _embed_single(self, image: Image.Image, bitstream: list[int]) -> Image.Image:
        y_channel, cb, cr = get_ycbcr_channels(image)
        blocks = get_blocks_8x8(y_channel)
        coefficients = get_embeddable_coefficients()
        capacity = len(blocks) * len(coefficients)
        if len(bitstream) > capacity:
            raise ValueError(f"DCT capacity ({capacity} bits) cannot hold payload ({len(bitstream)} bits)")

        bit_idx = 0
        processed_blocks = []
        for block in blocks:
            shifted_block = block - 128.0
            dct_coeffs = forward_dct_8x8(shifted_block)
            for r, c in coefficients:
                if bit_idx < len(bitstream):
                    dct_coeffs[r, c] = embed_bit(
                        dct_coeffs[r, c], bitstream[bit_idx], step=self.Q_STEP, context=dct_coeffs
                    )
                    bit_idx += 1
            processed_blocks.append(inverse_dct_8x8(dct_coeffs) + 128.0)

        final_image = reconstruct_image(
            reconstruct_y_channel(processed_blocks, original_y=y_channel), cb, cr
        )
        return self._correction_pass(final_image, bitstream, max_iterations=5)

    def _embed_distributed(self, image: Image.Image, bitstream: list[int]) -> Image.Image:
        """Embed a complete robust frame in every deterministic region."""
        carrier = image.convert("RGB").copy()
        regions = regions_for(carrier)
        coefficients = get_embeddable_coefficients()
        frame_capacity = min(
            (r.width // 8) * (r.height // 8) * len(coefficients) for r in regions
        )
        if len(bitstream) > frame_capacity:
            raise ValueError(
                f"Distributed DCT region capacity ({frame_capacity} bits) cannot hold "
                f"payload ({len(bitstream)} bits). Use a larger image."
            )

        for region in regions:
            crop = carrier.crop((region.x, region.y, region.x + region.width, region.y + region.height))
            embedded = self._embed_single(crop, bitstream)
            carrier.paste(embedded, (region.x, region.y))
        return carrier

    def _correction_pass(self, image: Image.Image, bitstream: list[int], max_iterations: int = 5) -> Image.Image:
        best_image = image
        best_error_count = float("inf")
        for _ in range(max_iterations):
            y_channel, cb, cr = get_ycbcr_channels(image)
            blocks = get_blocks_8x8(y_channel)
            coefficients = get_embeddable_coefficients()
            bit_idx = 0
            error_count = 0
            processed_blocks = []
            for block in blocks:
                shifted = block - 128.0
                dct_coeffs = forward_dct_8x8(shifted)
                for r, c in coefficients:
                    if bit_idx >= len(bitstream):
                        break
                    extracted = extract_bit(dct_coeffs[r, c], step=self.Q_STEP, context=dct_coeffs)
                    if extracted != bitstream[bit_idx]:
                        error_count += 1
                        dct_coeffs[r, c] = embed_bit(
                            dct_coeffs[r, c], bitstream[bit_idx], step=self.Q_STEP, context=dct_coeffs
                        )
                    bit_idx += 1
                processed_blocks.append(inverse_dct_8x8(dct_coeffs) + 128.0)
            if error_count == 0:
                return image
            image = reconstruct_image(
                reconstruct_y_channel(processed_blocks, original_y=y_channel), cb, cr
            )
            if error_count < best_error_count:
                best_error_count = error_count
                best_image = image
        return best_image

    def capacity(self, image: Image.Image) -> int:
        y_channel, _, _ = get_ycbcr_channels(image)
        coefficients = get_embeddable_coefficients()
        if not self.distributed:
            return len(get_blocks_8x8(y_channel)) * len(coefficients)
        regions = regions_for(image)
        return min((r.width // 8) * (r.height // 8) * len(coefficients) for r in regions)
