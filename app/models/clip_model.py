"""
Singleton CLIP model loader.

The CLIP model is ~350 MB. It is loaded ONCE on first use and reused.
open_clip is imported lazily so light API Lambdas can avoid the cold-start hit.
"""

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
        import open_clip
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        _model, _, _preprocess = open_clip.create_model_and_transforms(
            settings.clip_model_name,
            pretrained=settings.clip_pretrained,
            device=device,
        )

        _model.eval()
        try:
            _tokenizer = open_clip.get_tokenizer(settings.clip_model_name)
        except Exception as e:
            print(f"CLIP tokenizer unavailable (image-only mode): {e}")
            _tokenizer = None

        print(f"CLIP model loaded on {device}")

    return _model, _preprocess, _tokenizer
