"""
Lightweight FastAPI app for API Lambda (no CLIP import on cold start).

Routes: health, embedding enqueue, delete, queue admin, reindex.
Search stays on SearchFunction (full app.main).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from app.config import settings, validate_runtime_security
from app.middleware.auth import InternalAPIKeyMiddleware

# Refuse to start without service authentication.
validate_runtime_security()

api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Product Match API (light)...")
    if settings.database_url:
        try:
            from app.services.pgvector_service import ensure_collection

            ensure_collection()
        except Exception as e:
            print(f"WARNING: ensure_collection failed: {e}")
    print("API ready.")
    yield


app = FastAPI(
    title="Everystore Product Match API",
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

# Import router pieces without pulling search/CLIP:
# product create/delete, system, reindex via a light router
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks

from app.config import settings as _settings
from app.controllers import product_controller, reindex_controller, system_controller
from app.schemas.requests import (
    EmbeddingResponse,
    DeleteResponse,
    ReindexResponse,
    HealthResponse,
)

router = APIRouter()


@router.post("/products/embedding", status_code=202, response_model=EmbeddingResponse, tags=["Products"])
async def create_embedding(
    background_tasks: BackgroundTasks,
    product_id: str = Form(...),
    image_path: str = Form(None),
    image_file: UploadFile = File(None),
    metadata: str = Form("{}"),
):
    return await product_controller.create_embedding(
        background_tasks, product_id, image_path, image_file, metadata
    )


@router.delete("/products/embedding/{product_id}", response_model=DeleteResponse, tags=["Products"])
async def remove_embedding(product_id: str):
    return await product_controller.remove_embedding(product_id)


@router.post("/products/reindex", response_model=ReindexResponse, tags=["System"])
async def start_reindex(background_tasks: BackgroundTasks):
    return await reindex_controller.start_reindex(background_tasks)


@router.get("/products/reindex/status", tags=["System"])
async def reindex_status():
    return await reindex_controller.get_reindex_status()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    return await system_controller.health_check()


@router.get("/queue/status", tags=["System"])
async def queue_status():
    return await system_controller.queue_status()


@router.get("/queue/dead-letters", tags=["System"])
async def dead_letters():
    return await system_controller.dead_letters()


@router.delete("/queue/dead-letters", tags=["System"])
async def clear_dead_letters():
    return await system_controller.clear_dead_letter_queue()


app.include_router(router)
