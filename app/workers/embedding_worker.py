"""
Background worker for embedding generation with persistent queue support.

All heavy AI work (loading images, generating CLIP embeddings)
runs here asynchronously, never blocking API responses.

Each task is tracked in a file-based queue:
1. Task is written to queue BEFORE processing starts
2. Task is removed from queue AFTER successful completion
3. If server crashes mid-task, the task remains in the queue
4. On next startup, pending tasks are automatically retried (max 3 times)
5. Permanently failed tasks are moved to a dead letter file
"""

import os
import httpx
import io
from PIL import Image

from app.services.embedding_service import (
    generate_embedding_from_path,
    generate_embedding_from_bytes,
)
from app.services.qdrant_service import upsert_embedding
from app.services.task_queue import enqueue_task, complete_task, fail_task


def process_from_path(product_id: str, image_path: str, metadata: dict):
    """
    Worker job: load image from disk, generate embedding, store in Qdrant.

    This runs asynchronously — product becomes searchable after completion.
    """
    # 1. Write task to persistent queue (deduplication handled inside)
    task_id = enqueue_task("embed_path", product_id, image_path=image_path, metadata=metadata)

    try:
        # 2. Do the heavy AI work
        embedding = generate_embedding_from_path(image_path)
        upsert_embedding(product_id, embedding, metadata)
        print(f"[Worker] Indexed {product_id} from {image_path}")

        # 3. Mark task as done (removes from queue)
        complete_task(task_id)

    except Exception as e:
        # Task stays in queue for retry on next startup (up to MAX_RETRIES)
        fail_task(task_id, str(e))
        print(f"[Worker] Failed to index {product_id}: {e}")


def process_from_bytes(product_id: str, image_bytes: bytes, metadata: dict):
    """
    Worker job: use uploaded bytes directly to generate embedding.

    Saves the bytes to a temp file first so the task can be retried
    from disk if the server crashes.
    """
    from app.config import settings

    # Save uploaded bytes to a temp file for crash recovery
    temp_dir = os.path.join("task_queue", "uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{product_id}.tmp.jpg")

    with open(temp_path, "wb") as f:
        f.write(image_bytes)

    # 1. Write task to persistent queue (with the saved file path)
    task_id = enqueue_task("embed_path", product_id, image_path=temp_path, metadata=metadata)

    try:
        # 2. Do the heavy AI work
        embedding = generate_embedding_from_bytes(image_bytes)
        upsert_embedding(product_id, embedding, metadata)
        print(f"[Worker] Indexed {product_id} from uploaded bytes")

        # 3. Mark task as done and clean up temp file
        complete_task(task_id)
        if os.path.exists(temp_path):
            os.remove(temp_path)

    except Exception as e:
        # Task stays in queue for retry on next startup (up to MAX_RETRIES)
        fail_task(task_id, str(e))
        print(f"[Worker] Failed {product_id}: {e}")


def process_from_url(product_id: str, image_url: str, metadata: dict):
    """
    Worker job: download image from URL, generate embedding, store in Qdrant.

    Downloads the image to a temp file for persistence/recovery.
    """
    # 1. Write task to persistent queue
    task_id = enqueue_task("embed_url", product_id, image_url=image_url, metadata=metadata)

    try:
        # 2. Download image
        print(f"[Worker] Downloading image for {product_id} from {image_url}...")
        response = httpx.get(image_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        image_bytes = response.content

        # Save to temp file for crash recovery (so we don't redownload on retry if we got this far)
        temp_dir = os.path.join("task_queue", "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"url_{product_id}.jpg")
        with open(temp_path, "wb") as f:
            f.write(image_bytes)

        # 3. Generate embedding
        embedding = generate_embedding_from_bytes(image_bytes)
        upsert_embedding(product_id, embedding, metadata)
        print(f"[Worker] Indexed {product_id} from URL {image_url}")

        # 4. Mark task as done and clean up
        complete_task(task_id)
        if os.path.exists(temp_path):
            os.remove(temp_path)

    except Exception as e:
        fail_task(task_id, str(e))
        print(f"[Worker] Failed {product_id} from URL: {e}")


def retry_pending_tasks():
    """
    Called on server startup to retry any tasks that were
    interrupted by a crash or shutdown.
    """
    from app.services.task_queue import get_pending_tasks

    pending = get_pending_tasks()
    if not pending:
        print("[Recovery] No pending tasks found. Queue is clean.")
        return

    print(f"[Recovery] Found {len(pending)} pending tasks. Retrying...")

    for task in pending:
        task_id = task["task_id"]
        product_id = task["product_id"]
        task_type = task.get("task_type", "embed_path")
        image_path = task.get("image_path")
        image_url = task.get("image_url")
        metadata = task.get("metadata", {})
        retries = task.get("retries", 0)

        print(f"[Recovery] Retrying {product_id} ({task_type}, attempt {retries + 1}/3)")

        try:
            if task_type == "embed_url" and image_url:
                # If it's a URL, we try to redownload (unless it was already saved to image_path)
                if image_path and os.path.exists(image_path):
                    embedding = generate_embedding_from_path(image_path)
                else:
                    response = httpx.get(image_url, timeout=30.0, follow_redirects=True)
                    response.raise_for_status()
                    embedding = generate_embedding_from_bytes(response.content)
            
            elif image_path and os.path.exists(image_path):
                embedding = generate_embedding_from_path(image_path)
            
            else:
                print(f"[Recovery] Skipping {task_id}: no valid source found")
                fail_task(task_id, "No valid image source found during recovery")
                continue

            upsert_embedding(product_id, embedding, metadata)
            complete_task(task_id)
            print(f"[Recovery] Successfully recovered {product_id}")

            # Clean up temp uploads
            if image_path and "uploads" in image_path and os.path.exists(image_path):
                os.remove(image_path)

        except Exception as e:
            fail_task(task_id, str(e))
            print(f"[Recovery] Failed to recover {product_id}: {e}")
