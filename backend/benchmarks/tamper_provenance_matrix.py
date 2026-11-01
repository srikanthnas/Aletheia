"""Small local benchmark for distributed DCT-QIM/RDM provenance resilience."""
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
from app.services.dct.dct_strategy import DCTStrategy
from app.services.dct.robust_codec import encode_robust, decode_robust, decode_header, frame_bit_length, HEADER_SIZE
from app.services.dct.distributed_layout import regions_for
from app.services.dct.qim_extractor import extract_bitstream
from app.services.embedding.mir_serializer import build_mir, serialize

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend" / "app" / "uploads" / "a59dda47-1efe-4a79-a207-3e85bd76ff64_dall_e_sample_2.jpg"
OUT = ROOT / "backend" / "benchmarks" / "results" / "tamper_provenance_matrix.txt"

def recover(image, expected):
    good = 0
    for r in regions_for(image):
        crop = image.crop((r.x, r.y, r.x+r.width, r.y+r.height))
        try:
            hb = extract_bitstream(crop, max_bits=HEADER_SIZE*14)
            _, n, _, _ = decode_header(hb)
            bits = extract_bitstream(crop, max_bits=frame_bit_length(n))
            payload, _ = decode_robust(bits)
            good += payload == expected
        except Exception:
            pass
    return good, len(regions_for(image))

def main():
    img = Image.open(SOURCE).convert("RGB")
    mir = build_mir("BENCH-001", "Gemini", "2026-09-12T00:00:00+00:00")
    expected = serialize(mir)
    embedded = DCTStrategy(distributed=True).embed(img, encode_robust(expected))
    tests = {
        "original": embedded,
        "brightness +5%": ImageEnhance.Brightness(embedded).enhance(1.05),
        "brightness +10%": ImageEnhance.Brightness(embedded).enhance(1.10),
        "brightness +20%": ImageEnhance.Brightness(embedded).enhance(1.20),
        "contrast +10%": ImageEnhance.Contrast(embedded).enhance(1.10),
        "contrast +20%": ImageEnhance.Contrast(embedded).enhance(1.20),
        "blur": embedded.filter(ImageFilter.GaussianBlur(1.0)),
        "jpeg 60": None,
        "local edit": None,
    }
    jpeg_path = OUT.with_suffix(".jpg")
    embedded.save(jpeg_path, quality=60)
    tests["jpeg 60"] = Image.open(jpeg_path).convert("RGB")
    local = embedded.copy()
    ImageDraw.Draw(local).rectangle((embedded.width//3, embedded.height//3, embedded.width//2, embedded.height//2), fill=(255, 0, 0))
    tests["local edit"] = local
    lines=[]
    for name, image in tests.items():
        good,total=recover(image, expected)
        lines.append(f"{name:20s} {good:2d}/{total:2d} regions recovered")
    OUT.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__": main()
