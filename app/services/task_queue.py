"""
Persistent file-based task queue.

Provides crash recovery for embedding jobs. Each pending task is written
to a JSON file on disk. When a task completes (or fails permanently),
it is removed from the queue. On server startup, any remaining tasks
in the queue are automatically retried.

Under normal operation the queue file is empty (no pending tasks).
"""

import json
import os
import threading
import time
from pathlib import Path

from app.config import settings

QUEUE_DIR = Path(settings.qdrant_path).parent / "task_queue"
QUEUE_FILE = QUEUE_DIR / "pending_tasks.json"

# Thread lock to prevent concurrent writes to the queue file
_lock = threading.Lock()


def _ensure_queue_dir():
    """Create the queue directory if it doesn't exist."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _read_queue() -> list[dict]:
    """Read all pending tasks from the queue file."""
    _ensure_queue_dir()
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _write_queue(tasks: list[dict]):
    """Write the full task list to the queue file atomically."""
    _ensure_queue_dir()
    # Write to a temp file first, then rename for atomicity
    tmp_file = QUEUE_FILE.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(tasks, f, indent=2)
    tmp_file.replace(QUEUE_FILE)


def enqueue_task(task_type: str, product_id: str, image_path: str | None = None,
                 metadata: dict | None = None) -> str:
    """
    Add a task to the persistent queue.

    Returns the task_id for tracking.
    """
    task_id = f"{product_id}_{int(time.time() * 1000)}"
    task = {
        "task_id": task_id,
        "task_type": task_type,  # "embed_path" or "embed_bytes"
        "product_id": product_id,
        "image_path": image_path,
        "metadata": metadata or {},
        "created_at": time.time(),
        "status": "pending",
    }

    with _lock:
        tasks = _read_queue()
        tasks.append(task)
        _write_queue(tasks)

    print(f"[Queue] Added task {task_id} ({task_type})")
    return task_id


def complete_task(task_id: str):
    """Remove a completed task from the queue."""
    with _lock:
        tasks = _read_queue()
        tasks = [t for t in tasks if t["task_id"] != task_id]
        _write_queue(tasks)

    print(f"[Queue] Completed task {task_id}")


def fail_task(task_id: str, error: str):
    """Mark a task as failed (keeps it in queue for retry on next startup)."""
    with _lock:
        tasks = _read_queue()
        for t in tasks:
            if t["task_id"] == task_id:
                t["status"] = "failed"
                t["error"] = error
                t["failed_at"] = time.time()
                break
        _write_queue(tasks)

    print(f"[Queue] Task {task_id} failed: {error}")


def get_pending_tasks() -> list[dict]:
    """Get all pending or failed tasks (for recovery on startup)."""
    with _lock:
        tasks = _read_queue()
    return [t for t in tasks if t["status"] in ("pending", "failed")]


def get_queue_status() -> dict:
    """Get a summary of the queue status."""
    with _lock:
        tasks = _read_queue()
    pending = sum(1 for t in tasks if t["status"] == "pending")
    failed = sum(1 for t in tasks if t["status"] == "failed")
    return {
        "total": len(tasks),
        "pending": pending,
        "failed": failed,
        "empty": len(tasks) == 0,
    }
