-- Neon / Postgres pgvector schema for product-match
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS product_embeddings (
    product_id TEXT PRIMARY KEY,
    embedding vector(512) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    image_url TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW cosine index (rebuild after bulk load if needed)
CREATE INDEX IF NOT EXISTS product_embeddings_embedding_hnsw_idx
    ON product_embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS product_embeddings_updated_at_idx
    ON product_embeddings (updated_at DESC);
