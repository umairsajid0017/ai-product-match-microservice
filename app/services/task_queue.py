"""
Persistent file-based task queue with retry limits and deduplication.

Provides crash recovery for embedding jobs. Each pending task is written
to a JSON file on disk. When a task completes (or fails permanently),
it is removed from the queue. On server startup, any remaining tasks
in the queue are automatically retried.

Features:
- Retry limit (MAX_RETRIES): Tasks that fail repeatedly are moved to
  a dead letter file for manual inspection.
- Deduplication: Only one pending task per product_id is allowed.
  New requests for the same product update the existing task.
- Atomic writes: Queue file is written to a temp file first, then renamed.

Under normal operation the queue file is empty (no pending tasks).
"""

import json
import threading
import time
from pathlib import Path

from app.config import settings

MAX_RETRIES = 3

QUEUE_DIR = Path(settings.qdrant_path).parent / "task_queue"
QUEUE_FILE = QUEUE_DIR / "pending_tasks.json"
DEAD_LETTER_FILE = QUEUE_DIR / "failed_tasks.json"

# Thread lock to prevent concurrent writes to the queue file
_lock = threading.Lock()


def _ensure_queue_dir():
    """Create the queue directory if it doesn't exist."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _read_file(filepath: Path) -> list[dict]:
    """Read a JSON list from a file."""
    _ensure_queue_dir()
    if not filepath.exists():
        return []
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _write_file(filepath: Path, tasks: list[dict]):
    """Write a JSON list to a file atomically."""
    _ensure_queue_dir()
    tmp_file = filepath.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(tasks, f, indent=2)
    tmp_file.replace(filepath)


def _read_queue() -> list[dict]:
    """Read all pending tasks from the queue file."""
    return _read_file(QUEUE_FILE)


def _write_queue(tasks: list[dict]):
    """Write the full task list to the queue file atomically."""
    _write_file(QUEUE_FILE, tasks)


def enqueue_task(task_type: str, product_id: str, image_path: str | None = None,
                 image_url: str | None = None, metadata: dict | None = None) -> str:
    """
    Add a task to the persistent queue.

    If a task for the same product_id already exists, it is replaced
    (deduplication). This prevents wasting CPU on redundant embeddings
    when Laravel sends multiple rapid requests for the same product.

    Returns the task_id for tracking.
    """
    task_id = f"{product_id}_{int(time.time() * 1000)}"
    task = {
        "task_id": task_id,
        "task_type": task_type,
        "product_id": product_id,
        "image_path": image_path,
        "image_url": image_url,
        "metadata": metadata or {},
        "created_at": time.time(),
        "status": "pending",
        "retries": 0,
    }

    with _lock:
        tasks = _read_queue()

        # Deduplication: remove any existing task for the same product_id
        existing = [t for t in tasks if t["product_id"] == product_id]
        if existing:
            tasks = [t for t in tasks if t["product_id"] != product_id]
            print(f"[Queue] Replaced existing task for product {product_id}")

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
    """
    Mark a task as failed and increment retry count.

    If retries exceed MAX_RETRIES, the task is moved to the dead letter
    file and removed from the active queue permanently.
    """
    with _lock:
        tasks = _read_queue()
        task_to_fail = None

        for t in tasks:
            if t["task_id"] == task_id:
                t["retries"] = t.get("retries", 0) + 1
                t["status"] = "failed"
                t["error"] = error
                t["failed_at"] = time.time()
                task_to_fail = t
                break

        if task_to_fail and task_to_fail["retries"] >= MAX_RETRIES:
            # Move to dead letter queue — stop retrying
            tasks = [t for t in tasks if t["task_id"] != task_id]
            _write_queue(tasks)

            dead_letters = _read_file(DEAD_LETTER_FILE)
            task_to_fail["moved_to_dead_letter_at"] = time.time()
            dead_letters.append(task_to_fail)
            _write_file(DEAD_LETTER_FILE, dead_letters)

            print(f"[Queue] Task {task_id} moved to dead letter after {MAX_RETRIES} retries: {error}")
            return True
        else:
            _write_queue(tasks)
            retries = task_to_fail["retries"] if task_to_fail else "?"
            print(f"[Queue] Task {task_id} failed (retry {retries}/{MAX_RETRIES}): {error}")
            return False


def get_pending_tasks() -> list[dict]:
    """Get all pending or failed tasks (for recovery on startup)."""
    with _lock:
        tasks = _read_queue()
    return [t for t in tasks if t["status"] in ("pending", "failed")]


def get_queue_status() -> dict:
    """Get a summary of the queue and dead letter status."""
    with _lock:
        tasks = _read_queue()
        dead_letters = _read_file(DEAD_LETTER_FILE)

    pending = sum(1 for t in tasks if t["status"] == "pending")
    failed = sum(1 for t in tasks if t["status"] == "failed")
    return {
        "total": len(tasks),
        "pending": pending,
        "failed": failed,
        "dead_letter": len(dead_letters),
        "empty": len(tasks) == 0,
    }


def get_dead_letters() -> list[dict]:
    """Get all tasks in the dead letter queue (for manual inspection)."""
    with _lock:
        return _read_file(DEAD_LETTER_FILE)


def clear_dead_letters():
    """Clear the dead letter queue after manual inspection."""
    with _lock:
        _write_file(DEAD_LETTER_FILE, [])
    print("[Queue] Dead letter queue cleared")
