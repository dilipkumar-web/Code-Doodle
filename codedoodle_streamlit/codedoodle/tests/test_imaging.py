import io

import pytest
from PIL import Image

from app.imaging import MAX_SIDE, prepare_image


def png(size, mode="RGB", color=(255, 255, 255)):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def test_large_images_are_shrunk_and_converted_to_jpeg():
    data, mime = prepare_image(png((4000, 3000)))
    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(data)).size) <= MAX_SIDE


def test_transparent_png_is_flattened_onto_white():
    data, _ = prepare_image(png((20, 20), "RGBA", (0, 0, 0, 0)))
    pixel = Image.open(io.BytesIO(data)).getpixel((10, 10))
    assert all(channel > 240 for channel in pixel)


def test_phone_rotation_is_applied():
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    exif = img.getexif()
    exif[0x0112] = 6  # "rotate 90 degrees clockwise to display"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    data, _ = prepare_image(buf.getvalue())
    assert Image.open(io.BytesIO(data)).size == (100, 200)


def test_garbage_is_rejected_with_a_readable_message():
    with pytest.raises(ValueError) as err:
        prepare_image(b"not really an image")
    assert "PNG, JPEG or WebP" in str(err.value)
