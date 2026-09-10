"""Decode and resize uploads before storing a small, metadata-free profile image."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


def prepare_avatar(upload):
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Profile images must be 5 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload, formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValidationError("Profile images must be 20 megapixels or smaller.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((512, 512))
                image.info.clear()
                output = BytesIO()
                image.save(output, format="WEBP", quality=85)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ValidationError("Upload a valid JPEG, PNG, or WebP image.")
