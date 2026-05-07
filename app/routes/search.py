"""
POST /products/search-similar

Called by your Laravel backend when a shopkeeper captures a photo.
This is the lightweight "online" path — generates one embedding
and does a fast vector lookup in Qdrant. No heavy processing.
"""

from fastapi import APIRouter, UploadFile, File, Form

from app.services.embedding_service import generate_embedding_from_bytes
from app.services.qdrant_service import search_similar
from app.config import settings
from app.schemas.requests import SearchResponse

router = APIRouter()


@router.post("/products/search-similar", response_model=SearchResponse)
async def search_by_image(
    image_file: UploadFile = File(...),
    top_k: int = Form(settings.default_top_k),
):
    """
    Search for visually similar products.

    Upload a photo captured by the shopkeeper's camera.
    Returns the top matching products with confidence scores.

    - Generates one embedding (~100-200ms on CPU)
    - Searches Qdrant (~<10ms for 10K products)
    - Returns matches above the similarity threshold (0.70)
    """
    image_bytes = await image_file.read()
    embedding = generate_embedding_from_bytes(image_bytes)
    matches = search_similar(embedding, top_k=top_k)

    return SearchResponse(matches=matches, count=len(matches))
