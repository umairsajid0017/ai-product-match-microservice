"""
POST /products/embedding

Called by your Laravel backend when a new product is created or image is uploaded.
Queues a background job to generate and store the embedding asynchronously.
This keeps the API response instant — heavy AI work happens in the worker.
"""

import json
import os

import redis
from rq import Queue
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import settings
from app.schemas.requests import EmbeddingResponse

router = APIRouter()

rq_client = redis.from_url(settings.redis_url)
queue = Queue(connection=rq_client)


@router.post("/products/embedding", status_code=202, response_model=EmbeddingResponse)
async def create_embedding(
    product_id: str = Form(...),
    image_path: str = Form(None),
    image_file: UploadFile = File(None),
    metadata: str = Form("{}"),
):
    """
    Index a product image for similarity search.

    Provide either `image_path` (relative path in IMAGE_BASE_PATH)
    OR `image_file` (upload the image directly), not both.

    The embedding is generated asynchronously by a background worker.
    """
    meta = json.loads(metadata)

    if image_file:
        image_bytes = await image_file.read()
        queue.enqueue(
            "app.workers.embedding_worker.process_from_bytes",
            product_id,
            image_bytes,
            meta,
        )
    elif image_path:
        full_path = os.path.join(settings.image_base_path, image_path)
        if not os.path.exists(full_path):
            raise HTTPException(400, f"Image not found: {image_path}")
        queue.enqueue(
            "app.workers.embedding_worker.process_from_path",
            product_id,
            full_path,
            meta,
        )
    else:
        raise HTTPException(400, "Provide image_path or image_file")

    return EmbeddingResponse(
        status="queued",
        product_id=product_id,
        message="Embedding job queued successfully",
    )
