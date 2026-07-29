"""
Reindexing logic (Controller).

On Lambda: fan-out existing Neon rows that have image_url back onto SQS.
Local (no SQS): still scan IMAGE_BASE_PATH when present.
"""

import os
import threading
import time
from fastapi import BackgroundTasks

from app.config import settings
from app.schemas.requests import ReindexResponse
from app.services.pgvector_service import list_embeddings_for_reindex
from app.services import sqs_queue

_reindex_state = {
    "running": False,
    "total": 0,
    "processed": 0,
    "failed": 0,
    "skipped": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_state_lock = threading.Lock()


def _update_state(**kwargs):
    with _state_lock:
        _reindex_state.update(kwargs)


async def start_reindex(background_tasks: BackgroundTasks):
    """Start reindex — SQS fan-out preferred."""
    with _state_lock:
        if _reindex_state["running"]:
            return ReindexResponse(status="reindex already in progress")

    if sqs_queue.is_sqs_enabled():
        rows = list_embeddings_for_reindex()
        if not rows:
            return ReindexResponse(
                status="reindex skipped — no embeddings with image_url to requeue"
            )

        enqueued = 0
        for row in rows:
            sqs_queue.enqueue_task(
                "embed_url",
                row["product_id"],
                image_url=row["image_url"],
                metadata=row.get("metadata") or {},
            )
            enqueued += 1

        _update_state(
            running=False,
            total=enqueued,
            processed=enqueued,
            failed=0,
            skipped=0,
            started_at=time.time(),
            finished_at=time.time(),
            error=None,
        )
        return ReindexResponse(
            status=f"reindex queued — {enqueued} products sent to SQS"
        )

    background_tasks.add_task(_local_reindex_task)
    return ReindexResponse(status="reindex started — live search unaffected")


async def get_reindex_status():
    with _state_lock:
        state = dict(_reindex_state)

    if state["total"] > 0:
        state["progress_percent"] = round(
            (state["processed"] + state["failed"] + state["skipped"])
            / state["total"]
            * 100,
            1,
        )
    else:
        state["progress_percent"] = 0

    if state["started_at"]:
        end = state["finished_at"] or time.time()
        state["elapsed_seconds"] = round(end - state["started_at"], 1)
    else:
        state["elapsed_seconds"] = 0

    return state


def _local_reindex_task():
    """Dev-only: scan IMAGE_BASE_PATH and upsert into Neon."""
    from app.services.embedding_service import generate_embedding_from_path
    from app.services.image_service import validate_image_path
    from app.services.pgvector_service import upsert_embedding

    base = settings.image_base_path

    if not os.path.isdir(base):
        _update_state(running=False, error=f"Image directory not found: {base}")
        return

    image_files = [
        f
        for f in os.listdir(base)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    total = len(image_files)
    _update_state(
        running=True,
        total=total,
        processed=0,
        failed=0,
        skipped=0,
        started_at=time.time(),
        finished_at=None,
        error=None,
    )

    for filename in image_files:
        product_id = os.path.splitext(filename)[0]
        full_path = os.path.join(base, filename)

        try:
            validate_image_path(full_path)
        except ValueError:
            _update_state(skipped=_reindex_state["skipped"] + 1)
            continue

        try:
            embedding = generate_embedding_from_path(full_path)
            upsert_embedding(str(product_id), embedding, {})
            _update_state(processed=_reindex_state["processed"] + 1)
        except Exception:
            _update_state(failed=_reindex_state["failed"] + 1)

    _update_state(running=False, finished_at=time.time())
