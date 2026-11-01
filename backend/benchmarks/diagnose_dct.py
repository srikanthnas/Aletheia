"""
diagnose_dct.py — Trace DCT-QIM embed/extract round-trip bit-by-bit.
"""
import sys
import numpy as np
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.dct.block_processor import get_ycbcr_channels, get_blocks_8x8, reconstruct_y_channel, reconstruct_image
from app.services.dct.dct_transform import forward_dct_8x8, inverse_dct_8x8
from app.services.dct.coefficient_selector import get_embeddable_coefficients
from app.services.dct.qim_embedder import embed_bit, extract_bit
from app.services.dct.dct_strategy import DCTStrategy
from app.services.dct.qim_extractor import extract_bitstream
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.embedding.binary_encoder import encode
from app.services.extraction.binary_decoder import bits_to_bytes
from app.services.extraction.mir_deserializer import deserialize


def run():
    base = Path(__file__).resolve().parent.parent.parent / "demo_assets" / "real"
    candidates = list(base.glob("*.jpg")) + list(base.glob("*.png"))
    source_path = candidates[0]
    original = Image.open(source_path).convert("RGB")
    print(f"Image: {source_path.name}  Size: {original.size}")

    mir = build_mir(media_id="test-001", model_name="Test", timestamp="2026-01-01T00:00:00Z")
    payload = serialize(mir)
    bitstream = encode(payload)
    total_bits = len(bitstream)
    print(f"Payload bytes: {len(payload)}  Bitstream bits: {total_bits}")

    # --- Embed ---
    strategy = DCTStrategy()
    embedded = strategy.embed(original, bitstream)

    # --- Extract immediately ---
    extracted = extract_bitstream(embedded, q_step=16.0)
    print(f"Extracted total bits: {len(extracted)}")

    # --- Compare header bits ---
    print(f"\nFirst 32 bits embedded : {bitstream[:32]}")
    print(f"First 32 bits extracted: {extracted[:32]}")

    header_errors = sum(a != b for a, b in zip(bitstream[:32], extracted[:32]))
    print(f"Header bit errors: {header_errors}/32")

    # Decode header from extracted
    n_bytes_from_extracted = 0
    for b in extracted[:32]:
        n_bytes_from_extracted = (n_bytes_from_extracted << 1) | b
    print(f"Declared n_bytes from extracted header: {n_bytes_from_extracted}  (expected: {len(payload)})")

    # --- Compare full payload ---
    total_errors = sum(a != b for a, b in zip(bitstream, extracted[:total_bits]))
    print(f"\nTotal bit errors in first {total_bits} bits: {total_errors}/{total_bits}")
    error_positions = [i for i, (a, b) in enumerate(zip(bitstream, extracted[:total_bits])) if a != b]
    if error_positions:
        print(f"First 20 error positions: {error_positions[:20]}")

    # --- Single-block diagnostic ---
    print("\n--- Single block embed/extract trace ---")
    y, cb, cr = get_ycbcr_channels(original)
    blocks = get_blocks_8x8(y)
    coefficients = get_embeddable_coefficients()

    block0 = blocks[0]
    shifted = block0 - 128.0
    dct0 = forward_dct_8x8(shifted)

    # Embed first 12 bits into block 0
    for idx, (r, c) in enumerate(coefficients):
        if idx < len(bitstream):
            orig_val = dct0[r, c]
            embedded_val = embed_bit(dct0[r, c], bitstream[idx], step=16.0)
            dct0[r, c] = embedded_val

    # Inverse DCT and back
    idct0 = inverse_dct_8x8(dct0)
    idct0_shifted = idct0 + 128.0

    # Re-extract
    re_y = y.copy()
    re_y[0:8, 0:8] = idct0_shifted
    re_image = reconstruct_image(re_y, cb, cr)

    re_y2, _, _ = get_ycbcr_channels(re_image)
    re_blocks = get_blocks_8x8(re_y2)
    re_block0 = re_blocks[0]
    re_shifted = re_block0 - 128.0
    re_dct0 = forward_dct_8x8(re_shifted)

    print("Bit idx | embedded? | orig coeff | after embed | after IDCT+DCT | extracted bit | expected bit")
    for idx, (r, c) in enumerate(coefficients):
        orig_coeff = blocks[0][r, c] - 128.0
        after_embed = embed_bit(orig_coeff, bitstream[idx], step=16.0)
        after_roundtrip = re_dct0[r, c]
        extracted = extract_bit(after_roundtrip, step=16.0)
        expected = bitstream[idx]
        mismatch = "  <-- MISMATCH" if extracted != expected else ""
        print(f"  [{idx:2d}] ({r},{c}) | exp={expected} | orig={orig_coeff:8.2f} | embed={after_embed:8.2f} | roundtrip={after_roundtrip:8.2f} | got={extracted}{mismatch}")


if __name__ == "__main__":
    run()
