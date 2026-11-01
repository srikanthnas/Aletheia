"""
diagnose_convergence.py — Test how many correction iterations are needed for zero errors.
"""
import sys
import io
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.dct.block_processor import get_ycbcr_channels, get_blocks_8x8, reconstruct_y_channel, reconstruct_image
from app.services.dct.dct_transform import forward_dct_8x8, inverse_dct_8x8
from app.services.dct.coefficient_selector import get_embeddable_coefficients
from app.services.dct.qim_embedder import embed_bit, extract_bit
from app.services.dct.qim_extractor import extract_bitstream
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.embedding.binary_encoder import encode


def count_errors(image: Image.Image, bitstream: list[int]) -> int:
    extracted = extract_bitstream(image, q_step=16.0)
    return sum(a != b for a, b in zip(bitstream, extracted[:len(bitstream)]))


def single_correction_pass(image: Image.Image, bitstream: list[int], q_step: float = 16.0) -> tuple[Image.Image, int]:
    """One correction pass. Returns (corrected_image, n_corrections_made)."""
    y_channel, cb, cr = get_ycbcr_channels(image)
    blocks = get_blocks_8x8(y_channel)
    coefficients = get_embeddable_coefficients()

    bit_idx = 0
    corrections = 0
    processed_blocks = []

    for block in blocks:
        shifted = block - 128.0
        dct_coeffs = forward_dct_8x8(shifted)
        for (r, c) in coefficients:
            if bit_idx >= len(bitstream):
                break
            extracted = extract_bit(dct_coeffs[r, c], step=q_step)
            if extracted != bitstream[bit_idx]:
                dct_coeffs[r, c] = embed_bit(dct_coeffs[r, c], bitstream[bit_idx], step=q_step)
                corrections += 1
            bit_idx += 1
        idct_block = inverse_dct_8x8(dct_coeffs)
        processed_blocks.append(idct_block + 128.0)

    y_recon = reconstruct_y_channel(processed_blocks, original_y=y_channel)
    return reconstruct_image(y_recon, cb, cr), corrections


def run():
    base = Path(__file__).resolve().parent.parent.parent / "demo_assets" / "real"
    candidates = list(base.glob("*.jpg")) + list(base.glob("*.png"))
    source_path = candidates[0]
    original = Image.open(source_path).convert("RGB")

    mir = build_mir(media_id="test-001", model_name="Test", timestamp="2026-01-01T00:00:00Z")
    payload = serialize(mir)
    bitstream = encode(payload)

    # Initial embed (no correction)
    from app.services.dct.dct_strategy import DCTStrategy
    strategy = DCTStrategy()

    # Patch to disable correction pass for this test
    from app.services.dct import block_processor, dct_transform, coefficient_selector
    from app.services.dct.qim_embedder import embed_bit as _embed_bit

    y_channel, cb, cr = get_ycbcr_channels(original)
    blocks = get_blocks_8x8(y_channel)
    coefficients = get_embeddable_coefficients()
    bit_idx = 0
    processed_blocks = []
    for block in blocks:
        shifted = block - 128.0
        dct_coeffs = dct_transform.forward_dct_8x8(shifted)
        for (r, c) in coefficients:
            if bit_idx < len(bitstream):
                dct_coeffs[r, c] = _embed_bit(dct_coeffs[r, c], bitstream[bit_idx], step=16.0)
                bit_idx += 1
        idct_block = dct_transform.inverse_dct_8x8(dct_coeffs)
        processed_blocks.append(idct_block + 128.0)
    y_recon = reconstruct_y_channel(processed_blocks, original_y=y_channel)
    image = reconstruct_image(y_recon, cb, cr)

    print(f"After initial embed: {count_errors(image, bitstream)} errors")

    for i in range(10):
        image, n_fixed = single_correction_pass(image, bitstream)
        errors = count_errors(image, bitstream)
        print(f"  Pass {i+1}: fixed={n_fixed}  remaining errors={errors}")
        if errors == 0:
            print(f"  Converged after {i+1} correction pass(es).")
            break
    else:
        print("  Did NOT converge in 10 passes.")


if __name__ == "__main__":
    run()
