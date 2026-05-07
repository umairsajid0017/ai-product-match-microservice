"""
Tests for the search endpoint.

Requires Qdrant and Redis to be running.
Run with: pytest tests/test_search.py -v
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

HEADERS = {"X-Internal-API-Key": "change-me-to-a-strong-secret"}


def test_health():
    """Health check should return 200 without API key."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_search_requires_image():
    """Search without image should return 422."""
    r = client.post("/products/search-similar", headers=HEADERS)
    assert r.status_code == 422


def test_search_returns_results():
    """Search with a valid image should return matches array."""
    # Create a minimal valid JPEG for testing
    import io
    from PIL import Image

    img = Image.new("RGB", (224, 224), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    r = client.post(
        "/products/search-similar",
        headers=HEADERS,
        files={"image_file": ("test.jpg", buf, "image/jpeg")},
        data={"top_k": 5},
    )

    assert r.status_code == 200
    data = r.json()
    assert "matches" in data
    assert "count" in data
    assert isinstance(data["matches"], list)
