"""Authentication fail-closed behaviour (ES-08)."""

import os

import pytest
from fastapi.testclient import TestClient

from app.config import (
    SecurityConfigurationError,
    settings,
    validate_runtime_security,
)
from app.main import app

client = TestClient(app)

VALID_KEY = os.environ["INTERNAL_API_KEY"]


def test_startup_rejects_an_absent_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "")

    with pytest.raises(SecurityConfigurationError):
        validate_runtime_security()


def test_startup_rejects_a_short_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "short-key")

    with pytest.raises(SecurityConfigurationError):
        validate_runtime_security()


def test_startup_rejects_a_placeholder_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "change-me-to-a-strong-secret")

    with pytest.raises(SecurityConfigurationError):
        validate_runtime_security()


def test_startup_accepts_a_configured_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", VALID_KEY)

    validate_runtime_security()


def test_missing_key_is_rejected():
    response = client.post("/products/embedding", data={"product_id": "x"})

    assert response.status_code == 403


def test_wrong_key_is_rejected():
    response = client.post(
        "/products/embedding",
        data={"product_id": "x"},
        headers={"X-Internal-API-Key": "wrong-key-value-0123456789"},
    )

    assert response.status_code == 403


def test_correct_key_reaches_the_handler():
    response = client.post(
        "/products/embedding",
        data={"product_id": "x"},
        headers={"X-Internal-API-Key": VALID_KEY},
    )

    # Reached the controller: it rejects the request for having no image.
    assert response.status_code == 400


def test_health_stays_public():
    assert client.get("/health").status_code == 200


def test_docs_are_not_public():
    assert client.get("/openapi.json").status_code == 403
