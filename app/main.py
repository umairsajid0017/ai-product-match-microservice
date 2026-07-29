"""
FastAPI application entry point.

Everystore AI Image Matching Microservice
- Lazy-loads CLIP on first use (search / worker)
- Ensures Neon pgvector table exists
- Registers API routes and security middleware
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from app.config import settings
from app.services.pgvector_service import ensure_collection
from app import api
from app.middleware.auth import InternalAPIKeyMiddleware

api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting AI Microservice...")
    if settings.database_url:
        ensure_collection()
    else:
        print("WARNING: DATABASE_URL not set — vector DB unavailable until configured")

    from app.workers.embedding_worker import retry_pending_tasks

    retry_pending_tasks()
    print("AI Microservice ready.")
    yield
    print("AI Microservice shutting down.")


app = FastAPI(
    title="Everystore Product Image Matching API",
    description=(
        "AI-assisted product matching microservice. "
        "Generates CLIP embeddings and performs vector similarity search via Neon pgvector."
    ),
    version="2.0.0",
    lifespan=lifespan,
    dependencies=[Depends(api_key_header)],
)

app.add_middleware(InternalAPIKeyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "DELETE", "GET"],
    allow_headers=["*"],
)

app.include_router(api.router)
