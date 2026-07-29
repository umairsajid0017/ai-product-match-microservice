"""
Neon Postgres + pgvector vector store.

Replaces Qdrant local mode for Lambda / multi-instance deployments.
Vectors are 512-d L2-normalized CLIP embeddings; cosine distance via <=>.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from pgvector.psycopg2 import register_vector

from app.config import settings

VECTOR_SIZE = 512

_pool_lock = threading.Lock()
_connection = None


def _require_database_url() -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for Neon pgvector")
    return settings.database_url


@contextmanager
def get_connection() -> Iterator[Any]:
    """
    Yield a registered psycopg2 connection.

    Neon serverless can drop idle connections; reconnect on failure.
    """
    global _connection
    with _pool_lock:
        try:
            if _connection is None or _connection.closed:
                _connection = psycopg2.connect(_require_database_url())
                _connection.autocommit = True
                register_vector(_connection)
            else:
                # Probe connection
                with _connection.cursor() as cur:
                    cur.execute("SELECT 1")
        except Exception:
            try:
                if _connection and not _connection.closed:
                    _connection.close()
            except Exception:
                pass
            _connection = psycopg2.connect(_require_database_url())
            _connection.autocommit = True
            register_vector(_connection)

        conn = _connection

    try:
        yield conn
    except psycopg2.OperationalError:
        with _pool_lock:
            try:
                if _connection and not _connection.closed:
                    _connection.close()
            except Exception:
                pass
            _connection = None
        raise


def ensure_collection(collection_name: str | None = None):
    """
    Ensure the product_embeddings table and extension exist.

    collection_name is accepted for API compatibility with the old Qdrant layer.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS product_embeddings (
                    product_id TEXT PRIMARY KEY,
                    embedding vector(%s) NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    image_url TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                (VECTOR_SIZE,),
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS product_embeddings_embedding_hnsw_idx
                ON product_embeddings
                USING hnsw (embedding vector_cosine_ops)
                """
            )
    print("pgvector table ready: product_embeddings")


def upsert_embedding(
    product_id: str,
    embedding: list[float],
    metadata: dict,
    collection_name: str | None = None,
    image_url: str | None = None,
):
    """Insert or update a product embedding."""
    if len(embedding) != VECTOR_SIZE:
        raise ValueError(f"Expected {VECTOR_SIZE}-d embedding, got {len(embedding)}")

    meta = dict(metadata or {})
    meta.setdefault("product_id", product_id)
    stored_url = image_url or meta.get("image_url")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO product_embeddings (product_id, embedding, metadata, image_url, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (product_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    image_url = COALESCE(EXCLUDED.image_url, product_embeddings.image_url),
                    updated_at = NOW()
                """,
                (str(product_id), embedding, Json(meta), stored_url),
            )


def search_similar(embedding: list[float], top_k: int = 10) -> list[dict]:
    """
    Cosine similarity search.

    pgvector <=> returns cosine distance; score = 1 - distance.
    """
    if len(embedding) != VECTOR_SIZE:
        raise ValueError(f"Expected {VECTOR_SIZE}-d embedding, got {len(embedding)}")

    threshold = settings.similarity_threshold

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    product_id,
                    metadata,
                    1 - (embedding <=> %s::vector) AS score
                FROM product_embeddings
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding, embedding, threshold, embedding, top_k),
            )
            rows = cur.fetchall()

    results = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        results.append(
            {
                "product_id": str(row["product_id"]),
                "score": float(row["score"]),
                "metadata": metadata or {},
            }
        )
    return results


def delete_embedding(product_id: str):
    """Remove a product embedding."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM product_embeddings WHERE product_id = %s",
                (str(product_id),),
            )


def get_collection_count(collection_name: str | None = None) -> int:
    """Return number of stored embeddings."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM product_embeddings")
            return int(cur.fetchone()[0])


def list_embeddings_for_reindex(limit: int = 10000) -> list[dict]:
    """Rows with image_url for reindex fan-out."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT product_id, image_url, metadata
                FROM product_embeddings
                WHERE image_url IS NOT NULL AND image_url <> ''
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    out = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        out.append(
            {
                "product_id": str(row["product_id"]),
                "image_url": row["image_url"],
                "metadata": metadata or {},
            }
        )
    return out


# --- Compatibility stubs (shadow reindex used file-local Qdrant) ---

SHADOW_COLLECTION = "product_embeddings_shadow"


def create_shadow_collection():
    """No-op for pgvector; reindex updates rows in place via SQS."""
    print("pgvector reindex uses in-place upserts (no shadow table)")


def swap_shadow_to_live():
    """No-op for pgvector."""
    print("pgvector reindex swap skipped (in-place)")


def drop_shadow_collection():
    """No-op for pgvector."""
    pass
