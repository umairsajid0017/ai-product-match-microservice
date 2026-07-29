"""
Background / worker embedding processing.

On Lambda: SQS Worker invokes process_task().
Locally: BackgroundTasks can still call process_from_* helpers.
"""

from __future__ import annotations

import base64
import os

import httpx

from app.config import settings
from app.services.embedding_service import (
    generate_embedding_from_bytes,
    generate_embedding_from_path,
)
from app.services.pgvector_service import upsert_embedding
from app.services import sqs_queue


def notify_laravel_callback(product_id: str, status: str):
    """Fire-and-forget INDEXED/FAILED webhook to Laravel."""
    callback_url = settings.laravel_callback_url
    if not callback_url:
        return

    try:
        response = httpx.post(
            callback_url,
            json={"product_id": str(product_id), "status": status},
            headers={
                "X-Internal-API-Key": settings.internal_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        print(
            f"[Callback] Notified Laravel: product {product_id} -> {status} "
            f"(HTTP {response.status_code})"
        )
    except Exception as e:
        print(f"[Callback] Failed to notify Laravel for product {product_id}: {e}")


def _index(
    product_id: str,
    embedding: list[float],
    metadata: dict,
    image_url: str | None = None,
):
    meta = dict(metadata or {})
    if image_url:
        meta["image_url"] = image_url
    upsert_embedding(str(product_id), embedding, meta, image_url=image_url)


def process_from_path(product_id: str, image_path: str, metadata: dict):
    """Local-path embedding (dev / optional)."""
    try:
        embedding = generate_embedding_from_path(image_path)
        _index(product_id, embedding, metadata)
        print(f"[Worker] Indexed {product_id} from {image_path}")
        notify_laravel_callback(product_id, "INDEXED")
    except Exception as e:
        notify_laravel_callback(product_id, "FAILED")
        print(f"[Worker] Failed to index {product_id}: {e}")
        raise


def process_from_bytes(
    product_id: str,
    image_bytes: bytes,
    metadata: dict,
    image_url: str | None = None,
):
    """Embed from raw bytes."""
    try:
        embedding = generate_embedding_from_bytes(image_bytes)
        _index(product_id, embedding, metadata, image_url=image_url)
        print(f"[Worker] Indexed {product_id} from bytes")
        notify_laravel_callback(product_id, "INDEXED")
    except Exception as e:
        notify_laravel_callback(product_id, "FAILED")
        print(f"[Worker] Failed {product_id}: {e}")
        raise


def process_from_url(product_id: str, image_url: str, metadata: dict):
    """Download image from URL, embed, store in Neon."""
    try:
        print(f"[Worker] Downloading image for {product_id} from {image_url}...")
        response = httpx.get(image_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        embedding = generate_embedding_from_bytes(response.content)
        _index(product_id, embedding, metadata, image_url=image_url)
        print(f"[Worker] Indexed {product_id} from URL {image_url}")
        notify_laravel_callback(product_id, "INDEXED")
    except Exception as e:
        notify_laravel_callback(product_id, "FAILED")
        print(f"[Worker] Failed {product_id} from URL: {e}")
        raise


def process_task(task: dict):
    """
    Process one SQS task payload.

    Supported sources (priority):
    - image_url / http image_path
    - s3_key (+ S3_BUCKET)
    - image_b64 (small payloads)
    - local image_path
    """
    product_id = str(task["product_id"])
    metadata = task.get("metadata") or {}
    image_url = task.get("image_url")
    image_path = task.get("image_path")
    s3_key = task.get("s3_key")
    image_b64 = task.get("image_b64")

    if image_url or (image_path and str(image_path).startswith(("http://", "https://"))):
        url = image_url or image_path
        process_from_url(product_id, url, metadata)
        return

    if s3_key:
        image_bytes = sqs_queue.download_s3_bytes(s3_key)
        process_from_bytes(product_id, image_bytes, metadata)
        return

    if image_b64:
        image_bytes = base64.b64decode(image_b64)
        process_from_bytes(product_id, image_bytes, metadata)
        return

    if image_path and os.path.exists(image_path):
        process_from_path(product_id, image_path, metadata)
        return

    raise ValueError(f"No valid image source for product {product_id}")


def retry_pending_tasks():
    """
    Local file-queue recovery stub.

    On Lambda, SQS / DLQ handles retries — no startup redrive needed.
    """
    if sqs_queue.is_sqs_enabled():
        print("[Recovery] SQS enabled — skipping local file-queue recovery")
        return
    print("[Recovery] No local pending-task recovery on Neon/SQS stack")
