"""
Image validation service.

Validates uploaded images before processing to prevent
corrupt files, unsupported formats, and oversized uploads.
"""

import io
from PIL import Image

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image(image_bytes: bytes, content_type: str):
    """
    Validate an uploaded image.

    Raises ValueError if:
    - Content type is not JPEG, PNG, or WebP
    - File size exceeds 10 MB
    - Image data is corrupt
    """
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported image type: {content_type}. Allowed: {ALLOWED_TYPES}")

    if len(image_bytes) > MAX_SIZE_BYTES:
        raise ValueError(f"Image too large: {len(image_bytes)} bytes (max {MAX_SIZE_BYTES})")

    # Verify the image data is not corrupt
    try:
        Image.open(io.BytesIO(image_bytes)).verify()
    except Exception as e:
        raise ValueError(f"Corrupt image data: {e}")
