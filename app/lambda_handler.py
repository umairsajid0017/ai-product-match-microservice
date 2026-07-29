"""
AWS Lambda entrypoints.

Handlers import apps lazily so ApiFunction does not load the heavy search stack.
"""

from __future__ import annotations

import json


def api_handler(event, context):
    from mangum import Mangum
    from app.main_api import app as api_app

    return Mangum(api_app, lifespan="auto")(event, context)


def handler(event, context):
    from mangum import Mangum
    from app.main import app as full_app

    return Mangum(full_app, lifespan="auto")(event, context)


def worker_handler(event, context):
    """SQS consumer for embedding jobs."""
    from app.workers.embedding_worker import process_task

    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId")
        try:
            body = record.get("body") or "{}"
            task = json.loads(body)
            print(
                f"[Worker] Processing task {task.get('task_id')} "
                f"product={task.get('product_id')}"
            )
            process_task(task)
        except Exception as e:
            print(f"[Worker] Failed message {message_id}: {e}")
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
