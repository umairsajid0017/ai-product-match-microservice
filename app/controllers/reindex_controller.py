"""
Reindexing logic (Controller).

Handles the zero-downtime reindexing process.
"""

import os
import threading
import time
from fastapi import BackgroundTasks

from app.config import settings
from app.schemas.requests import ReindexResponse
from app.services.embedding_service import generate_embedding_from_path
from app.services.image_service import validate_image_path
from app.services.qdrant_service import (
    create_shadow_collection,
    upsert_embedding,
    swap_shadow_to_live,
    drop_shadow_collection,
    SHADOW_COLLECTION,
)

# Global reindex state (thread-safe)
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
    """Thread-safe state update."""
    with _state_lock:
        _reindex_state.update(kwargs)


async def start_reindex(background_tasks: BackgroundTasks):
    """Start the reindex background task."""
    with _state_lock:
        if _reindex_state["running"]:
            return ReindexResponse(status="reindex already in progress")

    background_tasks.add_task(_reindex_task)
    return ReindexResponse(status="reindex started — live search unaffected")


async def get_reindex_status():
    """Get the current reindex progress."""
    with _state_lock:
        state = dict(_reindex_state)

    if state["total"] > 0:
        state["progress_percent"] = round(
            (state["processed"] + state["failed"] + state["skipped"]) / state["total"] * 100, 1
        )
    else:
        state["progress_percent"] = 0

    if state["started_at"]:
        end = state["finished_at"] or time.time()
        state["elapsed_seconds"] = round(end - state["started_at"], 1)
    else:
        state["elapsed_seconds"] = 0

    return state


def _reindex_task():
    """Internal task for reindexing."""
    base = settings.image_base_path

    if not os.path.isdir(base):
        _update_state(running=False, error=f"Image directory not found: {base}")
        return

    image_files = [
        f for f in os.listdir(base)
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

    try:
        create_shadow_collection()
    except Exception as e:
        _update_state(running=False, error=f"Failed to create shadow collection: {e}")
        return

    for i, filename in enumerate(image_files, 1):
        product_id = os.path.splitext(filename)[0]
        full_path = os.path.join(base, filename)

        try:
            validate_image_path(full_path)
        except ValueError:
            _update_state(skipped=_reindex_state["skipped"] + 1)
            continue

        try:
            embedding = generate_embedding_from_path(full_path)
            upsert_embedding(product_id, embedding, {}, collection_name=SHADOW_COLLECTION)
            _update_state(processed=_reindex_state["processed"] + 1)
        except Exception:
            _update_state(failed=_reindex_state["failed"] + 1)

    try:
        swap_shadow_to_live()
        _update_state(running=False, finished_at=time.time())
    except Exception as e:
        drop_shadow_collection()
        _update_state(running=False, error=f"Swap failed: {e}", finished_at=time.time())
