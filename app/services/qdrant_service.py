"""
Compatibility shim — vector store is Neon pgvector.
"""

from app.services.pgvector_service import (  # noqa: F401
    VECTOR_SIZE,
    SHADOW_COLLECTION,
    ensure_collection,
    upsert_embedding,
    search_similar,
    delete_embedding,
    get_collection_count,
    create_shadow_collection,
    swap_shadow_to_live,
    drop_shadow_collection,
    list_embeddings_for_reindex,
)
