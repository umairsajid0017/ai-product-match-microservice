"""Test environment defaults, applied before the app modules are imported."""

import os

os.environ.setdefault("INTERNAL_API_KEY", "test-internal-api-key-0123456789abcdef")
os.environ.setdefault("ALLOWED_IMAGE_HOSTS", "cdn.everystore.pk")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("SQS_QUEUE_URL", "")
os.environ.setdefault("SQS_DLQ_URL", "")
os.environ.setdefault("S3_BUCKET", "")
