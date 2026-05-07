"""
Qdrant vector database service.

Handles collection management, vector insert/update/delete, and
similarity search. Uses cosine distance with a configurable threshold.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)

from app.config import settings

# Initialize Qdrant in Local Mode (stores data in a local folder)
client = QdrantClient(path=settings.qdrant_path)

COLLECTION = settings.qdrant_collection
VECTOR_SIZE = 512  # ViT-B/32 output dimension


def ensure_collection():
    """Create Qdrant collection if it does not exist."""
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection: {COLLECTION}")
    else:
        print(f"Qdrant collection already exists: {COLLECTION}")


import hashlib

def _generate_stable_id(product_id: str) -> int:
    """Generate a stable 64-bit integer ID from a string."""
    hash_obj = hashlib.sha256(product_id.encode())
    # Take first 8 bytes for a 64-bit integer
    return int.from_bytes(hash_obj.digest()[:8], byteorder="big") % (2**63)


def upsert_embedding(product_id: str, embedding: list[float], metadata: dict):
    """Insert or update a product embedding in Qdrant."""
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=_generate_stable_id(product_id),
                vector=embedding,
                payload={"product_id": product_id, **metadata},
            )
        ],
    )


def search_similar(embedding: list[float], top_k: int = 10) -> list[dict]:
    """
    Search for similar product vectors.

    Returns list of matches above the similarity threshold, each containing:
    - product_id: str
    - score: float (cosine similarity, 0-1)
    - metadata: dict
    """
    # Use the newer query_points API which is more robust for local mode
    results = client.query_points(
        collection_name=COLLECTION,
        query=embedding,
        limit=top_k,
        with_payload=True,
    ).points

    return [
        {
            "product_id": r.payload.get("product_id"),
            "score": r.score,
            "metadata": r.payload,
        }
        for r in results
        if r.score >= settings.similarity_threshold
    ]


def delete_embedding(product_id: str):
    """Remove a product embedding when product is deleted."""
    client.delete(
        collection_name=COLLECTION,
        points_selector=[_generate_stable_id(product_id)],
    )
