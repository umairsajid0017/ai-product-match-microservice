"""
SQS-backed embedding task queue for Lambda deployments.

Replaces the local file-based task_queue for durable async work + DLQ.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings


def _sqs():
    return boto3.client("sqs", region_name=settings.aws_region or "ap-south-1")


def _s3():
    return boto3.client("s3", region_name=settings.aws_region or "ap-south-1")


def is_sqs_enabled() -> bool:
    return bool(settings.sqs_queue_url)


def enqueue_task(
    task_type: str,
    product_id: str,
    image_path: str | None = None,
    image_url: str | None = None,
    s3_key: str | None = None,
    metadata: dict | None = None,
) -> str:
    """
    Push an embedding job to SQS.

    Message body is JSON consumed by the Worker Lambda.
    """
    if not settings.sqs_queue_url:
        raise RuntimeError("SQS_QUEUE_URL is not configured")

    task_id = f"{product_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    body = {
        "task_id": task_id,
        "task_type": task_type,
        "product_id": str(product_id),
        "image_path": image_path,
        "image_url": image_url,
        "s3_key": s3_key,
        "metadata": metadata or {},
        "created_at": time.time(),
    }

    _sqs().send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=json.dumps(body),
        MessageAttributes={
            "product_id": {
                "DataType": "String",
                "StringValue": str(product_id),
            },
            "task_type": {
                "DataType": "String",
                "StringValue": task_type,
            },
        },
    )
    print(f"[SQS] Enqueued task {task_id} ({task_type})")
    return task_id


def stage_image_bytes(product_id: str, image_bytes: bytes, content_type: str | None = None) -> str:
    """
    Upload multipart image bytes to S3 for the worker to process.

    Returns the S3 object key.
    """
    if not settings.s3_bucket:
        raise RuntimeError(
            "S3_BUCKET is required to stage uploaded image_file for async embedding"
        )

    ext = "jpg"
    if content_type == "image/png":
        ext = "png"
    elif content_type == "image/webp":
        ext = "webp"

    key = f"embed-uploads/{product_id}/{uuid.uuid4().hex}.{ext}"
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type

    _s3().put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=image_bytes,
        **extra,
    )
    return key


def download_s3_bytes(s3_key: str) -> bytes:
    if not settings.s3_bucket:
        raise RuntimeError("S3_BUCKET is not configured")
    obj = _s3().get_object(Bucket=settings.s3_bucket, Key=s3_key)
    return obj["Body"].read()


def _approx_queue_attrs(queue_url: str) -> dict[str, int]:
    try:
        attrs = _sqs().get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        )["Attributes"]
        return {
            "messages": int(attrs.get("ApproximateNumberOfMessages", 0)),
            "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)),
        }
    except ClientError as e:
        print(f"[SQS] Failed to read queue attrs: {e}")
        return {"messages": 0, "in_flight": 0, "delayed": 0}


def get_queue_status() -> dict:
    """Approximate SQS queue status (mirrors old file-queue admin shape)."""
    if not settings.sqs_queue_url:
        return {
            "total": 0,
            "pending": 0,
            "failed": 0,
            "dead_letter": 0,
            "empty": True,
            "backend": "none",
        }

    main = _approx_queue_attrs(settings.sqs_queue_url)
    dlq = {"messages": 0}
    if settings.sqs_dlq_url:
        dlq = _approx_queue_attrs(settings.sqs_dlq_url)

    pending = main["messages"] + main["in_flight"] + main["delayed"]
    return {
        "total": pending,
        "pending": pending,
        "failed": 0,
        "dead_letter": dlq["messages"],
        "empty": pending == 0,
        "backend": "sqs",
        "sqs": {
            "visible": main["messages"],
            "in_flight": main["in_flight"],
            "delayed": main["delayed"],
        },
    }


def get_dead_letters(max_messages: int = 10) -> list[dict]:
    """
    Peek DLQ messages (receive without long delete — messages become invisible briefly).

    For admin inspection parity with the old file DLQ.
    """
    if not settings.sqs_dlq_url:
        return []

    resp = _sqs().receive_message(
        QueueUrl=settings.sqs_dlq_url,
        MaxNumberOfMessages=min(max_messages, 10),
        VisibilityTimeout=5,
        WaitTimeSeconds=0,
    )
    tasks = []
    for msg in resp.get("Messages", []):
        try:
            body = json.loads(msg["Body"])
        except json.JSONDecodeError:
            body = {"raw": msg["Body"]}
        body["sqs_message_id"] = msg.get("MessageId")
        body["sqs_receipt_handle"] = msg.get("ReceiptHandle")
        tasks.append(body)
    return tasks


def clear_dead_letters(max_batches: int = 20) -> int:
    """Purge DLQ (or drain up to max_batches receive/delete cycles). Prefer PurgeQueue."""
    if not settings.sqs_dlq_url:
        return 0

    try:
        _sqs().purge_queue(QueueUrl=settings.sqs_dlq_url)
        print("[SQS] Dead letter queue purged")
        return -1  # unknown count after purge
    except ClientError as e:
        # Purge limited to once per 60s — fall back to drain
        print(f"[SQS] Purge failed ({e}); draining messages")
        deleted = 0
        for _ in range(max_batches):
            resp = _sqs().receive_message(
                QueueUrl=settings.sqs_dlq_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=0,
                VisibilityTimeout=30,
            )
            messages = resp.get("Messages", [])
            if not messages:
                break
            for msg in messages:
                _sqs().delete_message(
                    QueueUrl=settings.sqs_dlq_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
                deleted += 1
        return deleted
