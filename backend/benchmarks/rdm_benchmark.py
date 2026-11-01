"""
rdm_benchmark.py — Compare AC-QIM vs RDM-QIM across a set of attacks.

Run from the backend/ directory:
    python benchmarks/rdm_benchmark.py

Outputs a Markdown comparison table and per-row raw numbers.
"""

import sys
import io
import time
import math
from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Pipeline imports ─────────────────────────────────────────────────────────
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.embedding.binary_encoder import encode
from app.services.extraction.binary_decoder import bits_to_bytes
from app.services.extraction.mir_deserializer import deserialize

from app.services.dct.block_processor import (
    get_ycbcr_channels, get_blocks_8x8, reconstruct_y_channel, reconstruct_image
)
from app.services.dct.dct_transform import forward_dct_8x8, inverse_dct_8x8
from app.services.dct.coefficient_selector import get_embeddable_coefficients
from app.services.dct import qim_embedder                    # current version (RDM)
from app.services.dct.qim_extractor import extract_bitstream
from app.services.dct.dct_strategy import DCTStrategy


# ── Helpers ───────────────────────────────────────────────────────────────────

def psnr(original: Image.Image, watermarked: Image.Image) -> float:
    a = np.array(original, dtype=float)
    b = np.array(watermarked, dtype=float)
    mse = np.mean((a - b) ** 2)
    if mse == 0:
        return float("inf")
    return 10 * math.log10(255 ** 2 / mse)


def count_errors(embedded: Image.Image, bitstream: list, q_step: float) -> int:
    extracted = extract_bitstream(embedded, q_step=q_step)
    return sum(a != b for a, b in zip(bitstream, extracted[: len(bitstream)]))


def try_deserialize(embedded: Image.Image, bitstream: list, q_step: float):
    """Return (errors, success, media_id_or_error_msg)."""
    errors = count_errors(embedded, bitstream, q_step)
    extracted = extract_bitstream(embedded, q_step=q_step)
    n_bytes = 0
    for b in extracted[:32]:
        n_bytes = (n_bytes << 1) | b
    try:
        pb = bits_to_bytes(extracted[32: 32 + n_bytes * 8])
        mir = deserialize(pb)
        return errors, True, mir.media_id
    except Exception as e:
        return errors, False, str(e)[:50]


def jpeg_transform(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def apply_attack(embedded: Image.Image, name: str) -> Image.Image:
    if name == "Lossless":
        return embedded
    elif name == "Brightness +5%":
        return ImageEnhance.Brightness(embedded).enhance(1.05)
    elif name == "Brightness +10%":
        return ImageEnhance.Brightness(embedded).enhance(1.10)
    elif name == "Brightness +20%":
        return ImageEnhance.Brightness(embedded).enhance(1.20)
    elif name == "Contrast +10%":
        return ImageEnhance.Contrast(embedded).enhance(1.10)
    elif name == "JPEG 90":
        return jpeg_transform(embedded, 90)
    elif name == "JPEG 80":
        return jpeg_transform(embedded, 80)
    else:
        raise ValueError(f"Unknown attack: {name}")


# ── Legacy AC-QIM embed (bypasses RDM, uses standard QIM without context) ────

def _embed_legacy_qim(img: Image.Image, bitstream: list, q_step: float = 16.0) -> Image.Image:
    """Embed using plain AC-QIM (no RDM context normalization)."""
    y, cb, cr = get_ycbcr_channels(img)
    blocks = get_blocks_8x8(y)
    coefficients = get_embeddable_coefficients()
    bit_idx = 0
    processed = []
    for block in blocks:
        shifted = block - 128.0
        dct_c = forward_dct_8x8(shifted)
        for (r, c) in coefficients:
            if bit_idx < len(bitstream):
                # No context → standard QIM fallback path
                dct_c[r, c] = qim_embedder.embed_bit(
                    dct_c[r, c], bitstream[bit_idx], step=q_step
                )
                bit_idx += 1
        processed.append(inverse_dct_8x8(dct_c) + 128.0)
    y2 = reconstruct_y_channel(processed, y)
    return reconstruct_image(y2, cb, cr)


def _extract_legacy_qim(img: Image.Image, q_step: float = 16.0) -> list:
    """Extract using plain AC-QIM (no RDM context normalization)."""
    y, _, _ = get_ycbcr_channels(img)
    blocks = get_blocks_8x8(y)
    coefficients = get_embeddable_coefficients()
    bitstream = []
    for block in blocks:
        shifted = block - 128.0
        dct_c = forward_dct_8x8(shifted)
        for (r, c) in coefficients:
            bitstream.append(qim_embedder.extract_bit(dct_c[r, c], step=q_step))
    return bitstream


def count_errors_legacy(embedded: Image.Image, bitstream: list, q_step: float) -> int:
    extracted = _extract_legacy_qim(embedded, q_step)
    return sum(a != b for a, b in zip(bitstream, extracted[: len(bitstream)]))


# ── Main benchmark ────────────────────────────────────────────────────────────

def run():
    base = Path(__file__).resolve().parent.parent.parent / "demo_assets" / "real"
    candidates = list(base.glob("*.jpg")) + list(base.glob("*.png"))
    if not candidates:
        print("ERROR: No images found in demo_assets/real/")
        sys.exit(1)
    source_path = candidates[0]
    original = Image.open(source_path).convert("RGB")
    print(f"Source image: {source_path.name}  Size: {original.size}")

    mir = build_mir(
        media_id="benchmark-rdm-001",
        model_name="BenchmarkModel",
        timestamp="2026-08-04T00:00:00Z",
    )
    payload = serialize(mir)
    bitstream = encode(payload)
    total_bits = len(bitstream)
    Q_STEP = 16.0
    print(f"Payload: {total_bits} bits  ({len(payload)} bytes)\n")

    ATTACKS = [
        "Lossless",
        "Brightness +5%",
        "Brightness +10%",
        "Brightness +20%",
        "Contrast +10%",
        "JPEG 90",
        "JPEG 80",
    ]

    results = {}

    # ── Legacy AC-QIM ────────────────────────────────────────────────────────
    print("Embedding with AC-QIM (no RDM)...")
    t0 = time.perf_counter()
    emb_legacy = _embed_legacy_qim(original, bitstream, Q_STEP)
    t1 = time.perf_counter()
    legacy_embed_ms = (t1 - t0) * 1000
    legacy_psnr = psnr(original, emb_legacy)

    results["AC-QIM"] = {}
    for attack in ATTACKS:
        attacked = apply_attack(emb_legacy, attack)
        t0 = time.perf_counter()
        errors = count_errors_legacy(attacked, bitstream, Q_STEP)
        t1 = time.perf_counter()
        extract_ms = (t1 - t0) * 1000
        # try to deserialize
        extracted = _extract_legacy_qim(attacked, Q_STEP)
        n_bytes = 0
        for b in extracted[:32]:
            n_bytes = (n_bytes << 1) | b
        success = False
        if n_bytes == len(payload):
            try:
                deserialize(bits_to_bytes(extracted[32: 32 + n_bytes * 8]))
                success = True
            except Exception:
                pass
        results["AC-QIM"][attack] = {
            "errors": errors,
            "total": total_bits,
            "success": success,
            "extract_ms": extract_ms,
        }

    # ── RDM-QIM ──────────────────────────────────────────────────────────────
    print("Embedding with RDM-QIM...")
    strategy = DCTStrategy()
    t0 = time.perf_counter()
    emb_rdm = strategy.embed(original, bitstream)
    t1 = time.perf_counter()
    rdm_embed_ms = (t1 - t0) * 1000
    rdm_psnr = psnr(original, emb_rdm)

    results["RDM-QIM"] = {}
    for attack in ATTACKS:
        attacked = apply_attack(emb_rdm, attack)
        t0 = time.perf_counter()
        errors = count_errors(attacked, bitstream, Q_STEP)
        t1 = time.perf_counter()
        extract_ms = (t1 - t0) * 1000
        extracted = extract_bitstream(attacked, q_step=Q_STEP)
        n_bytes = 0
        for b in extracted[:32]:
            n_bytes = (n_bytes << 1) | b
        success = False
        if n_bytes == len(payload):
            try:
                deserialize(bits_to_bytes(extracted[32: 32 + n_bytes * 8]))
                success = True
            except Exception:
                pass
        results["RDM-QIM"][attack] = {
            "errors": errors,
            "total": total_bits,
            "success": success,
            "extract_ms": extract_ms,
        }

    # ── Print report ─────────────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("  WATERMARKING ROBUSTNESS COMPARISON: AC-QIM  vs  RDM-QIM")
    print("=" * 90)
    print(f"\n  Source: {source_path.name}  |  Payload: {total_bits} bits")
    print(f"  AC-QIM  embed: {legacy_embed_ms:6.1f} ms  PSNR: {legacy_psnr:.2f} dB")
    print(f"  RDM-QIM embed: {rdm_embed_ms:6.1f} ms  PSNR: {rdm_psnr:.2f} dB")
    print()

    col_w = 13
    header = (
        f"{'Attack':<22} | "
        f"{'AC-QIM Errors':>{col_w}} | "
        f"{'AC-QIM OK':>{col_w}} | "
        f"{'RDM Errors':>{col_w}} | "
        f"{'RDM OK':>{col_w}} | "
        f"{'Delta Errors':>{col_w}}"
    )
    print(header)
    print("-" * len(header))

    for attack in ATTACKS:
        lq = results["AC-QIM"][attack]
        rq = results["RDM-QIM"][attack]
        l_err = lq["errors"]
        r_err = rq["errors"]
        delta = l_err - r_err   # positive = RDM improved
        l_ok = "PASS" if lq["success"] else "FAIL"
        r_ok = "PASS" if rq["success"] else "FAIL"
        l_str = f"{l_err}/{lq['total']}"
        r_str = f"{r_err}/{rq['total']}"
        d_str = f"+{delta}" if delta > 0 else str(delta)
        print(
            f"{attack:<22} | "
            f"{l_str:>{col_w}} | "
            f"{l_ok:>{col_w}} | "
            f"{r_str:>{col_w}} | "
            f"{r_ok:>{col_w}} | "
            f"{d_str:>{col_w}}"
        )

    print()
    print(f"  PSNR comparison: AC-QIM={legacy_psnr:.2f} dB  RDM-QIM={rdm_psnr:.2f} dB")
    print(f"  Embed time:      AC-QIM={legacy_embed_ms:.1f} ms  RDM-QIM={rdm_embed_ms:.1f} ms")
    print("=" * 90)


if __name__ == "__main__":
    run()
