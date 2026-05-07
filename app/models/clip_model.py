"""
Singleton CLIP model loader.

The CLIP model is ~350 MB. It is loaded ONCE on startup and reused
for all subsequent requests. Never instantiate per-request.
"""

import open_clip
import torch
from app.config import settings

_model = None
_preprocess = None
_tokenizer = None


def get_model():
    """
    Returns (model, preprocess, tokenizer).
    Loads the model on first call; reuses on subsequent calls.
    """
    global _model, _preprocess, _tokenizer

    if _model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

        _model, _, _preprocess = open_clip.create_model_and_transforms(
            settings.clip_model_name,
            pretrained=settings.clip_pretrained,
            device=device,
        )

        _model.eval()  # inference-only mode — saves memory
        _tokenizer = open_clip.get_tokenizer(settings.clip_model_name)

        print(f"CLIP model loaded on {device}")

    return _model, _preprocess, _tokenizer
