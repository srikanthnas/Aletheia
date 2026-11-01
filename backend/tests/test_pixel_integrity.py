from PIL import Image, ImageEnhance

from app.services.verification.pixel_hash_service import generate_pixel_hash


def test_pixel_hash_matches_untouched_image():
    image = Image.new("RGB", (32, 32), (120, 80, 40))
    assert generate_pixel_hash(image) == generate_pixel_hash(image.copy())


def test_pixel_hash_detects_brightness_change():
    image = Image.new("RGB", (32, 32), (120, 80, 40))
    changed = ImageEnhance.Brightness(image).enhance(1.05)
    assert generate_pixel_hash(image) != generate_pixel_hash(changed)
