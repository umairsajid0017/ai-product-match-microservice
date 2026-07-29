"""
Product-related logic (Controller).

Handles embedding creation, similarity search, and deletion.
"""

import json
import os
from fastapi import UploadFile, HTTPException, BackgroundTasks

from app.config import settings
from app.services.image_service import validate_image_bytes, validate_image_path
from app.services.pgvector_service import search_similar, delete_embedding
from app.services import sqs_queue
from app.schemas.requests import EmbeddingResponse, SearchResponse, DeleteResponse


async def create_embedding(
    background_tasks: BackgroundTasks,
    product_id: str,
    image_path: str | None,
    image_file: UploadFile | None,
    metadata: str,
):
    """Business logic for indexing a product image."""
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(
            400,
            "Invalid JSON in 'metadata' field. "
            "Keys must use double quotes, e.g.: {\"product_name\": \"blue_juice\"}"
        )

    use_sqs = sqs_queue.is_sqs_enabled()

    if image_file:
        image_bytes = await image_file.read()

        try:
            validate_image_bytes(image_bytes, image_file.content_type)
        except ValueError as e:
            raise HTTPException(400, str(e))

        if use_sqs:
            try:
                s3_key = sqs_queue.stage_image_bytes(
                    product_id, image_bytes, image_file.content_type
                )
                sqs_queue.enqueue_task(
                    "embed_s3",
                    product_id,
                    s3_key=s3_key,
                    metadata=meta,
                )
            except Exception as e:
                raise HTTPException(500, f"Failed to queue embedding: {e}")
        else:
            from app.workers.embedding_worker import process_from_bytes

            background_tasks.add_task(process_from_bytes, product_id, image_bytes, meta)

    elif image_path:
        if image_path.startswith(("http://", "https://")):
            if use_sqs:
                try:
                    sqs_queue.enqueue_task(
                        "embed_url",
                        product_id,
                        image_url=image_path,
                        metadata=meta,
                    )
                except Exception as e:
                    raise HTTPException(500, f"Failed to queue embedding: {e}")
            else:
                from app.workers.embedding_worker import process_from_url

                background_tasks.add_task(
                    process_from_url,
                    product_id,
                    image_path,
                    meta,
                )
        else:
            full_path = os.path.join(settings.image_base_path, image_path)

            try:
                validate_image_path(full_path)
            except ValueError as e:
                raise HTTPException(400, str(e))

            if use_sqs:
                raise HTTPException(
                    400,
                    "Local image_path is not supported when SQS is enabled. "
                    "Provide an http(s) URL or upload image_file.",
                )
            from app.workers.embedding_worker import process_from_path

            background_tasks.add_task(process_from_path, product_id, full_path, meta)
    else:
        raise HTTPException(400, "Provide image_path or image_file")

    return EmbeddingResponse(
        status="queued",
        product_id=product_id,
        message="Embedding job queued successfully",
    )


async def search_by_image(image_file: UploadFile, top_k: int):
    """Business logic for similarity search."""
    from app.services.embedding_service import generate_embedding_from_bytes

    image_bytes = await image_file.read()
    try:
        validate_image_bytes(image_bytes, image_file.content_type)
    except ValueError as e:
        raise HTTPException(400, str(e))

    embedding = generate_embedding_from_bytes(image_bytes)
    matches = search_similar(embedding, top_k=top_k)

    return SearchResponse(matches=matches, count=len(matches))


async def remove_embedding(product_id: str):
    """Business logic for removing an embedding."""
    delete_embedding(product_id)
    return DeleteResponse(status="deleted", product_id=product_id)
