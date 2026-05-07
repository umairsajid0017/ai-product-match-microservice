"""
FastAPI application entry point.

Everystore AI Image Matching Microservice
- Loads CLIP model once on startup (singleton)
- Ensures Qdrant collection exists (Local mode)
- Registers all API routes and security middleware
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.qdrant_service import ensure_collection
from app.models.clip_model import get_model
from app.routes import embedding, search, reindex, delete
from app.middleware.auth import InternalAPIKeyMiddleware
from app.schemas.requests import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle.

    Startup:
    - Pre-loads CLIP model (~5-15s) so first request isn't slow
    - Ensures Qdrant collection exists

    This is critical — cold-loading the model on first request causes timeouts.
    """
    print("Loading CLIP model...")
    get_model()
    ensure_collection()
    print("AI Microservice ready.")
    yield
    # Shutdown: nothing needed
    print("AI Microservice shutting down.")


app = FastAPI(
    title="Everystore Product Image Matching API",
    description=(
        "Lightweight AI-assisted product matching microservice. "
        "Generates CLIP embeddings and performs vector similarity search."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Security: API key middleware
app.add_middleware(InternalAPIKeyMiddleware)

# CORS: restrict to your Laravel backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to your Laravel backend URL in production
    allow_methods=["POST", "DELETE", "GET"],
    allow_headers=["*"],
)

# Register routes
app.include_router(embedding.router)
app.include_router(search.router)
app.include_router(reindex.router)
app.include_router(delete.router)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint for load balancers."""
    return HealthResponse(status="ok")
