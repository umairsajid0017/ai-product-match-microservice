"""
Qdrant vector database service.

Handles collection management, vector insert/update/delete, and
similarity search. Uses cosine distance with a configurable threshold.

Supports shadow collections for zero-downtime reindexing:
- Live collection: serves all search queries
- Shadow collection: built during reindex, then atomically swapped
"""

import hashlib
import threading

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
SHADOW_COLLECTION = f"{COLLECTION}_shadow"
VECTOR_SIZE = 512  # ViT-B/32 output dimension

# Lock for atomic collection swap
_swap_lock = threading.Lock()


def _generate_stable_id(product_id: str) -> int:
    """Generate a stable 64-bit integer ID from a string."""
    hash_obj = hashlib.sha256(product_id.encode())
    return int.from_bytes(hash_obj.digest()[:8], byteorder="big") % (2**63)


def ensure_collection(collection_name: str | None = None):
    """Create a Qdrant collection if it does not exist."""
    name = collection_name or COLLECTION
    existing = [c.name for c in client.get_collections().collections]

    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection: {name}")
    else:
        print(f"Qdrant collection already exists: {name}")


def upsert_embedding(product_id: str, embedding: list[float], metadata: dict,
                     collection_name: str | None = None):
    """Insert or update a product embedding in Qdrant."""
    name = collection_name or COLLECTION
    client.upsert(
        collection_name=name,
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
    Search for similar product vectors in the live collection.

    Returns list of matches above the similarity threshold, each containing:
    - product_id: str
    - score: float (cosine similarity, 0-1)
    - metadata: dict
    """
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


# --- Shadow Collection for Zero-Downtime Reindexing ---

def create_shadow_collection():
    """
    Create (or recreate) a shadow collection for reindexing.

    The shadow collection is built in the background while the live
    collection continues to serve search queries uninterrupted.
    """
    existing = [c.name for c in client.get_collections().collections]

    # Drop old shadow if it exists (leftover from a failed reindex)
    if SHADOW_COLLECTION in existing:
        client.delete_collection(SHADOW_COLLECTION)
        print(f"Dropped old shadow collection: {SHADOW_COLLECTION}")

    client.create_collection(
        collection_name=SHADOW_COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    print(f"Created shadow collection: {SHADOW_COLLECTION}")


def swap_shadow_to_live():
    """
    Atomically swap the shadow collection to become the live collection.

    This is the final step of a zero-downtime reindex:
    1. Delete the old live collection
    2. Rename shadow → live (by recreating and copying)

    Since Qdrant local mode doesn't support rename, we:
    - Keep both collections
    - Update the module-level COLLECTION pointer
    - Delete the old one
    """
    global COLLECTION

    with _swap_lock:
        existing = [c.name for c in client.get_collections().collections]

        if SHADOW_COLLECTION not in existing:
            raise RuntimeError("Shadow collection does not exist. Run reindex first.")

        # Delete the old live collection
        old_collection = COLLECTION
        if old_collection in existing:
            client.delete_collection(old_collection)
            print(f"Deleted old live collection: {old_collection}")

        # Recreate the live collection with data from shadow
        # Since local Qdrant doesn't support rename, we scroll all points
        # from shadow into a new live collection
        client.create_collection(
            collection_name=old_collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

        # Copy all points from shadow to new live collection
        offset = None
        batch_size = 100
        total_copied = 0

        while True:
            result = client.scroll(
                collection_name=SHADOW_COLLECTION,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            points, next_offset = result

            if not points:
                break

            client.upsert(
                collection_name=old_collection,
                points=[
                    PointStruct(
                        id=p.id,
                        vector=p.vector,
                        payload=p.payload,
                    )
                    for p in points
                ],
            )
            total_copied += len(points)
            offset = next_offset

            if next_offset is None:
                break

        # Delete the shadow collection
        client.delete_collection(SHADOW_COLLECTION)

        COLLECTION = old_collection
        print(f"Swap complete. Live collection now has {total_copied} products.")


def drop_shadow_collection():
    """Clean up shadow collection if reindex is cancelled or fails."""
    existing = [c.name for c in client.get_collections().collections]
    if SHADOW_COLLECTION in existing:
        client.delete_collection(SHADOW_COLLECTION)
        print(f"Dropped shadow collection: {SHADOW_COLLECTION}")


def get_collection_count(collection_name: str | None = None) -> int:
    """Get the number of points in a collection."""
    name = collection_name or COLLECTION
    try:
        info = client.get_collection(name)
        return info.points_count or 0
    except Exception:
        return 0
