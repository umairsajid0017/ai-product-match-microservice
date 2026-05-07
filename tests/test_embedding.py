"""
Tests for the embedding endpoints.

Requires Redis to be running for the queue.
Run with: pytest tests/test_embedding.py -v
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

HEADERS = {"X-Internal-API-Key": "change-me-to-a-strong-secret"}


def test_embedding_requires_image():
    """Embedding without image_path or image_file should return 400."""
    r = client.post(
        "/products/embedding",
        headers=HEADERS,
        data={"product_id": "test_001"},
    )
    assert r.status_code == 400


def test_embedding_with_file():
    """Embedding with a valid image file should return 202 queued."""
    import io
    from PIL import Image

    img = Image.new("RGB", (224, 224), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    r = client.post(
        "/products/embedding",
        headers=HEADERS,
        files={"image_file": ("test.jpg", buf, "image/jpeg")},
        data={
            "product_id": "test_001",
            "metadata": '{"name": "Test Product", "category": "test"}',
        },
    )

    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["product_id"] == "test_001"


def test_delete_embedding():
    """Delete endpoint should return 200."""
    r = client.delete(
        "/products/embedding/test_001",
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "deleted"
    assert data["product_id"] == "test_001"


def test_auth_required():
    """Requests without API key should be rejected."""
    r = client.post(
        "/products/search-similar",
        files={"image_file": ("test.jpg", b"fake", "image/jpeg")},
    )
    assert r.status_code == 403
