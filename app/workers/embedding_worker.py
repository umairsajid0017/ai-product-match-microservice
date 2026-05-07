"""
Redis Queue background worker for embedding generation.

This is the "offline processing" half of the architecture.
All heavy AI work (loading images, generating CLIP embeddings)
runs here asynchronously, never blocking API responses.

Run with: rq worker --url redis://localhost:6379
"""

from app.services.embedding_service import (
    generate_embedding_from_path,
    generate_embedding_from_bytes,
)
from app.services.qdrant_service import upsert_embedding


def process_from_path(product_id: str, image_path: str, metadata: dict):
    """
    Worker job: load image from disk, generate embedding, store in Qdrant.

    This runs asynchronously — product becomes searchable after completion.
    """
    try:
        embedding = generate_embedding_from_path(image_path)
        upsert_embedding(product_id, embedding, metadata)
        print(f"[Worker] Indexed {product_id} from {image_path}")
    except Exception as e:
        print(f"[Worker] Failed to index {product_id}: {e}")
        raise  # RQ will mark job as failed and can retry


def process_from_bytes(product_id: str, image_bytes: bytes, metadata: dict):
    """
    Worker job: use uploaded bytes directly to generate embedding.

    This runs asynchronously — product becomes searchable after completion.
    """
    try:
        embedding = generate_embedding_from_bytes(image_bytes)
        upsert_embedding(product_id, embedding, metadata)
        print(f"[Worker] Indexed {product_id} from uploaded bytes")
    except Exception as e:
        print(f"[Worker] Failed {product_id}: {e}")
        raise
