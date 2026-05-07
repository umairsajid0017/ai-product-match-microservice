"""
DELETE /products/embedding/{product_id}

Called by your Laravel backend when a product is deleted.
Removes the product vector from Qdrant so it no longer appears in search results.
"""

from fastapi import APIRouter

from app.services.qdrant_service import delete_embedding
from app.schemas.requests import DeleteResponse

router = APIRouter()


@router.delete("/products/embedding/{product_id}", response_model=DeleteResponse)
async def remove_embedding(product_id: str):
    """Remove a product embedding from Qdrant."""
    delete_embedding(product_id)
    return DeleteResponse(status="deleted", product_id=product_id)
