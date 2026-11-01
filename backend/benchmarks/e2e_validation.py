"""
e2e_validation.py — Phase 5 end-to-end validation of DCT-QIM production integration.

Tests:
  1. Lossless round-trip (embed → extract / verify)
  2. Brightness +10%
  3. JPEG 90% compression
  4. Contrast +10%
"""
import sys
import io
from pathlib import Path
from PIL import Image, ImageEnhance

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.dct.dct_strategy import DCTStrategy
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.embedding.binary_encoder import encode
from app.services.dct.qim_extractor import extract_bitstream
from app.services.extraction.binary_decoder import bits_to_bytes
from app.services.extraction.mir_deserializer import deserialize


Q_STEP = 16.0
STRATEGY_NAME = DCTStrategy.STRATEGY_NAME


def _build_bitstream(model_name: str = "TestModel", media_id: str = "test-uuid-001") -> list[int]:
    mir = build_mir(media_id=media_id, model_name=model_name, timestamp="2026-08-04T00:00:00Z")
    payload = serialize(mir)
    return encode(payload), mir


def _embed(image: Image.Image, bitstream: list[int]) -> Image.Image:
    strategy = DCTStrategy()
    cap = strategy.capacity(image)
    assert len(bitstream) <= cap, f"Payload too large: {len(bitstream)} > {cap}"
    return strategy.embed(image, bitstream)


def _try_extract(image: Image.Image, label: str, original_media_id: str) -> bool:
    bits = extract_bitstream(image, q_step=Q_STEP)
    if len(bits) < 32:
        print(f"  [{label}] FAIL — fewer than 32 bits extracted")
        return False

    n_bytes = 0
    for b in bits[:32]:
        n_bytes = (n_bytes << 1) | b

    if n_bytes == 0 or n_bytes > 1_048_576:
        print(f"  [{label}] FAIL — header claims {n_bytes} bytes (corrupt)")
        return False

    needed = n_bytes * 8
    if len(bits) < 32 + needed:
        print(f"  [{label}] FAIL — bitstream too short ({len(bits)} < {32 + needed})")
        return False

    payload_bits = bits[32: 32 + needed]
    try:
        payload_bytes = bits_to_bytes(payload_bits)
        mir = deserialize(payload_bytes)
    except Exception as exc:
        print(f"  [{label}] FAIL — deserialization error: {exc}")
        return False

    if mir.media_id != original_media_id:
        print(f"  [{label}] FAIL — media_id mismatch: got {mir.media_id!r}, expected {original_media_id!r}")
        return False

    print(f"  [{label}] PASS — media_id={mir.media_id!r} model={mir.model_name!r}")
    return True


def run():
    # Load a test image from demo_assets/real
    base = Path(__file__).resolve().parent.parent.parent / "demo_assets" / "real"
    candidates = list(base.glob("*.jpg")) + list(base.glob("*.png"))
    if not candidates:
        print("No test images found in demo_assets/real/ — aborting.")
        sys.exit(1)

    source_path = candidates[0]
    print(f"\nSource image: {source_path.name}")
    original = Image.open(source_path).convert("RGB")
    print(f"  Size: {original.size}  Mode: {original.mode}")

    bitstream, mir = _build_bitstream()
    media_id = mir.media_id
    print(f"  Payload: {len(bitstream)} bits  |  Strategy: {STRATEGY_NAME}\n")

    # 1. Embed
    embedded = _embed(original, bitstream)
    print(f"Embedded image size: {embedded.size}")

    # 2. Test: lossless round-trip (in-memory — no extra color conversion)
    print("\n[Test 1] Lossless in-memory round-trip")
    _try_extract(embedded, "Lossless in-memory", media_id)

    # 3. Test: Brightness +10%
    print("\n[Test 2] Brightness +10%")
    bright = ImageEnhance.Brightness(embedded).enhance(1.10)
    _try_extract(bright, "Brightness +10%", media_id)

    # 4. Test: JPEG 90% compression
    print("\n[Test 3] JPEG quality=90")
    jbuf = io.BytesIO()
    embedded.save(jbuf, format="JPEG", quality=90)
    jbuf.seek(0)
    jpeg_img = Image.open(jbuf).convert("RGB")
    _try_extract(jpeg_img, "JPEG q=90", media_id)

    # 5. Test: Contrast +10%
    print("\n[Test 4] Contrast +10%")
    contrast = ImageEnhance.Contrast(embedded).enhance(1.10)
    _try_extract(contrast, "Contrast +10%", media_id)

    print()


if __name__ == "__main__":
    run()
