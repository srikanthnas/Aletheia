from PIL import Image, ImageEnhance, ImageDraw

from app.services.dct.dct_strategy import DCTStrategy
from app.services.dct.robust_codec import encode_robust, decode_robust
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.dct.distributed_layout import regions_for
from app.services.dct.qim_extractor import extract_bitstream
from app.services.dct.robust_codec import decode_header, frame_bit_length, HEADER_SIZE


def _recover_count(image, expected):
    count = 0
    for r in regions_for(image):
        crop = image.crop((r.x, r.y, r.x + r.width, r.y + r.height))
        try:
            hb = extract_bitstream(crop, max_bits=HEADER_SIZE * 14)
            _, n, _, _ = decode_header(hb)
            bits = extract_bitstream(crop, max_bits=frame_bit_length(n))
            payload, _ = decode_robust(bits)
            count += payload == expected
        except Exception:
            pass
    return count


def test_robust_codec_corrects_scattered_errors():
    payload = b"Aletheia" * 20
    bits = encode_robust(payload)
    for i in [3, 41, 79, 117, 155, 193, 231, 269]:
        bits[i] ^= 1
    recovered, meta = decode_robust(bits)
    assert recovered == payload
    assert meta["corrected_codewords"] >= 1


def test_distributed_dct_recovers_untouched_and_local_tamper():
    image = Image.new("RGB", (512, 512), (100, 120, 140))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 470, 470), outline=(220, 220, 220), width=6)
    mir = build_mir("TEST", "Gemini", "2026-09-12T00:00:00+00:00")
    payload = serialize(mir)
    bits = encode_robust(payload)
    embedded = DCTStrategy(distributed=True).embed(image, bits)
    assert _recover_count(embedded, payload) == len(regions_for(embedded))

    tampered = embedded.copy()
    ImageDraw.Draw(tampered).rectangle((200, 200, 320, 320), fill=(255, 0, 0))
    recovered = _recover_count(tampered, payload)
    assert recovered < len(regions_for(tampered))
    assert recovered >= len(regions_for(tampered)) - 4
