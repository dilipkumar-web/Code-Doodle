"""Gets an uploaded photo ready to send to the model."""

import io

from PIL import Image, ImageOps

MAX_SIDE = 1600  # phone photos are huge; this keeps requests fast and pen lines readable


def prepare_image(raw: bytes) -> tuple:
    """Return (jpeg_bytes, mime_type).

    Fixes phone rotation, puts transparent PNGs on white, and shrinks the long
    side to MAX_SIDE. Raises ValueError with a message the user can act on.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            flat = Image.new("RGB", rgba.size, (255, 255, 255))
            flat.paste(rgba, mask=rgba.split()[-1])
            img = flat
        else:
            img = img.convert("RGB")
    except Exception as exc:
        raise ValueError("That file could not be read as an image. Use a PNG, JPEG or WebP photo.") from exc

    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue(), "image/jpeg"
