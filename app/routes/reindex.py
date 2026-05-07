"""
POST /products/reindex

Admin endpoint. Rebuilds all embeddings from scratch.
Use when switching models or after bulk image updates.
Scans IMAGE_BASE_PATH and queues embedding jobs for all found images.
"""

import os

import redis
from rq import Queue
from fastapi import APIRouter, BackgroundTasks

from app.config import settings
from app.schemas.requests import ReindexResponse

router = APIRouter()

rq_client = redis.from_url(settings.redis_url)
queue = Queue(connection=rq_client)


@router.post("/products/reindex", response_model=ReindexResponse)
async def reindex_all(background_tasks: BackgroundTasks):
    """
    Scan IMAGE_BASE_PATH and queue embedding jobs for all found images.

    This runs in the background — returns immediately.
    Monitor the worker logs to see progress.
    """
    background_tasks.add_task(_reindex_task)
    return ReindexResponse(status="reindex started")


def _reindex_task():
    """Background task that scans the image directory and queues jobs."""
    base = settings.image_base_path
    count = 0

    if not os.path.isdir(base):
        print(f"[Reindex] ERROR: Image directory not found: {base}")
        return

    for filename in os.listdir(base):
        if filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            product_id = os.path.splitext(filename)[0]
            full_path = os.path.join(base, filename)
            queue.enqueue(
                "app.workers.embedding_worker.process_from_path",
                product_id,
                full_path,
                {},
            )
            count += 1

    print(f"[Reindex] Queued {count} images for embedding generation")
