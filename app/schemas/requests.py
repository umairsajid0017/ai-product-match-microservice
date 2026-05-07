"""
Pydantic request/response models for the API.
"""

from pydantic import BaseModel


class EmbeddingResponse(BaseModel):
    """Response for POST /products/embedding"""
    status: str
    product_id: str
    message: str


class SearchMatch(BaseModel):
    """A single search result with confidence score."""
    product_id: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    """Response for POST /products/search-similar"""
    matches: list[SearchMatch]
    count: int


class DeleteResponse(BaseModel):
    """Response for DELETE /products/embedding/{product_id}"""
    status: str
    product_id: str


class ReindexResponse(BaseModel):
    """Response for POST /products/reindex"""
    status: str


class HealthResponse(BaseModel):
    """Response for GET /health"""
    status: str
