"""Shop-scoped similarity retrieval without external services or model loading."""

import asyncio
import io
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.controllers import product_controller
from app.services import pgvector_service


def test_shop_scope_is_forwarded_before_similarity_limit(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.services.embedding_service", SimpleNamespace(
        generate_embedding_from_bytes=lambda _: [0.0] * 512
    ))
    monkeypatch.setattr(product_controller, "validate_image_bytes", lambda *_: None)
    captured = {}

    def search(embedding, top_k, product_ids):
        captured.update(top_k=top_k, product_ids=product_ids)
        return [{"product_id": "42", "score": 0.9, "metadata": {}}]

    monkeypatch.setattr(product_controller, "search_similar", search)
    result = asyncio.run(product_controller.search_by_image(
        UploadFile(filename="earbuds.jpg", file=io.BytesIO(b"photo")), 10, '["42", "43"]'
    ))
    assert captured == {"top_k": 10, "product_ids": ["42", "43"]}
    assert result.count == 1


@pytest.mark.parametrize("scope", ['{}', '[true]', '["42 OR 1=1"]', 'not-json'])
def test_invalid_scopes_are_rejected(monkeypatch, scope):
    monkeypatch.setitem(sys.modules, "app.services.embedding_service", SimpleNamespace())
    with pytest.raises(HTTPException) as error:
        asyncio.run(product_controller.search_by_image(
            UploadFile(filename="earbuds.jpg", file=io.BytesIO()), 10, scope
        ))
    assert error.value.status_code == 422


def test_vector_query_binds_product_scope_before_limit(monkeypatch):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    connection = MagicMock()
    connection.cursor.return_value = cursor

    @contextmanager
    def connect():
        yield connection

    monkeypatch.setattr(pgvector_service, "get_connection", connect)
    pgvector_service.search_similar([0.0] * 512, 10, ["42"])
    sql, bindings = cursor.execute.call_args.args
    assert "product_id = ANY(%s::text[])" in sql
    assert bindings[3:5] == (["42"], ["42"])
    assert bindings[-1] == 10


def test_empty_shop_scope_does_not_query_other_shops(monkeypatch):
    monkeypatch.setattr(pgvector_service, "get_connection", lambda: pytest.fail("Unexpected database query"))
    assert pgvector_service.search_similar([0.0] * 512, 10, []) == []
