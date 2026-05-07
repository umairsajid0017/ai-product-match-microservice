"""
FastAPI application entry point.

Everystore AI Image Matching Microservice
- Loads CLIP model once on startup (singleton)
- Ensures Qdrant collection exists (Local mode)
- Recovers any interrupted tasks from the persistent queue
- Registers all API routes (from api.py) and security middleware
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from app.services.qdrant_service import ensure_collection
from app.models.clip_model import get_model
from app import api
from app.middleware.auth import InternalAPIKeyMiddleware
from app.workers.embedding_worker import retry_pending_tasks

# Define the API Key header scheme for Swagger UI
api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle.
    """
    print("Loading CLIP model...")
    get_model()
    ensure_collection()

    # Recover interrupted tasks from persistent queue
    retry_pending_tasks()

    print("AI Microservice ready.")
    yield
    print("AI Microservice shutting down.")


app = FastAPI(
    title="Everystore Product Image Matching API",
    description=(
        "Lightweight AI-assisted product matching microservice. "
        "Generates CLIP embeddings and performs vector similarity search."
    ),
    version="1.1.0",
    lifespan=lifespan,
    dependencies=[Depends(api_key_header)],
)

# Security: API key middleware
app.add_middleware(InternalAPIKeyMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "DELETE", "GET"],
    allow_headers=["*"],
)

# Register the central API router
app.include_router(api.router)
