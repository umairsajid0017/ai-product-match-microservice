"""
Embedding generation service.

All functions produce a 512-dimensional normalized float vector
from a product image. The embedding is generated ONCE per product
and stored in Qdrant for reuse.
"""

import io

import torch
import numpy as np
from PIL import Image

from app.models.clip_model import get_model


def generate_embedding_from_path(image_path: str) -> list[float]:
    """Load image from disk and return CLIP embedding."""
    image = Image.open(image_path).convert("RGB")
    return generate_embedding_from_image(image)


def generate_embedding_from_bytes(image_bytes: bytes) -> list[float]:
    """Accept raw bytes (camera upload) and return CLIP embedding."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return generate_embedding_from_image(image)


def generate_embedding_from_image(image: Image.Image) -> list[float]:
    """
    Core function: preprocess image → CLIP encode → L2 normalize → return vector.

    Returns a 512-dimensional float list (for ViT-B/32).
    """
    model, preprocess, _ = get_model()
    device = next(model.parameters()).device

    tensor = preprocess(image).unsqueeze(0).to(device)

    with torch.no_grad():
        features = model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)  # L2 normalize

    return features.cpu().numpy().flatten().tolist()
