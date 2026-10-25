"""
Image validation service.

Validates images before processing to prevent corrupt files,
unsupported formats, and oversized uploads from entering the queue.
This saves expensive CLIP inference time on bad data.
"""

import io
import os
from PIL import Image

from app.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _check_pixel_budget(source) -> None:
    """Reject decompression bombs before inference runs."""
    with Image.open(source) as img:
        width, height = img.size

    if width * height > settings.max_image_pixels:
        raise ValueError(
            f"Image dimensions are too large: {width}x{height} "
            f"(max {settings.max_image_pixels} pixels)"
        )


def validate_image_bytes(image_bytes: bytes, content_type: str | None = None):
    """
    Validate uploaded image bytes.

    Raises ValueError if:
    - Content type is not JPEG, PNG, or WebP (when provided)
    - File size exceeds 10 MB
    - Image data is corrupt or unreadable
    """
    if content_type and content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported image type: {content_type}. Allowed: {ALLOWED_TYPES}")

    if len(image_bytes) > MAX_SIZE_BYTES:
        raise ValueError(f"Image too large: {len(image_bytes)} bytes (max {MAX_SIZE_BYTES})")

    # Verify the image data is not corrupt
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        _check_pixel_budget(io.BytesIO(image_bytes))
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Corrupt image data: {e}")


def validate_image_path(image_path: str):
    """
    Validate an image file on disk before queuing.

    Raises ValueError if:
    - File does not exist
    - File extension is not supported
    - File size exceeds 10 MB
    - Image data is corrupt or unreadable
    """
    if not os.path.exists(image_path):
        raise ValueError(f"Image file not found: {image_path}")

    # Check extension
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Check file size
    file_size = os.path.getsize(image_path)
    if file_size > MAX_SIZE_BYTES:
        raise ValueError(f"Image too large: {file_size} bytes (max {MAX_SIZE_BYTES})")

    # Verify image integrity
    try:
        img = Image.open(image_path)
        img.verify()
        _check_pixel_budget(image_path)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Corrupt image file: {e}")
