"""
Central route definitions (The "One Place").

Registers all API endpoints and maps them to their respective controllers.
Follows a clean separation of concerns: Routes here, Logic in Controllers.
"""

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends

from app.config import settings
from app.controllers import product_controller, reindex_controller, system_controller
from app.schemas.requests import (
    EmbeddingResponse,
    SearchResponse,
    DeleteResponse,
    ReindexResponse,
    HealthResponse,
)

router = APIRouter()

# --- Product Endpoints ---

@router.post("/products/embedding", status_code=202, response_model=EmbeddingResponse, tags=["Products"])
async def create_embedding(
    background_tasks: BackgroundTasks,
    product_id: str = Form(...),
    image_path: str = Form(None),
    image_file: UploadFile = File(None),
    metadata: str = Form("{}"),
):
    """Index a product image for similarity search."""
    return await product_controller.create_embedding(
        background_tasks, product_id, image_path, image_file, metadata
    )


@router.post("/products/search-similar", response_model=SearchResponse, tags=["Products"])
async def search_by_image(
    image_file: UploadFile = File(...),
    top_k: int = Form(settings.default_top_k),
):
    """Search for visually similar products."""
    return await product_controller.search_by_image(image_file, top_k)


@router.delete("/products/embedding/{product_id}", response_model=DeleteResponse, tags=["Products"])
async def remove_embedding(product_id: str):
    """Remove a product embedding from Qdrant."""
    return await product_controller.remove_embedding(product_id)


# --- Reindex Endpoints ---

@router.post("/products/reindex", response_model=ReindexResponse, tags=["System"])
async def start_reindex(background_tasks: BackgroundTasks):
    """Rebuild all embeddings using a shadow collection (Zero-Downtime)."""
    return await reindex_controller.start_reindex(background_tasks)


@router.get("/products/reindex/status", tags=["System"])
async def reindex_status():
    """Get the current reindex progress."""
    return await reindex_controller.get_reindex_status()


# --- System & Monitoring Endpoints ---

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Health check endpoint."""
    return await system_controller.health_check()


@router.get("/queue/status", tags=["System"])
async def queue_status():
    """Check the persistent task queue status."""
    return await system_controller.queue_status()


@router.get("/queue/dead-letters", tags=["System"])
async def dead_letters():
    """View tasks that permanently failed after retries."""
    return await system_controller.dead_letters()


@router.delete("/queue/dead-letters", tags=["System"])
async def clear_dead_letters():
    """Clear the dead letter queue."""
    return await system_controller.clear_dead_letter_queue()
