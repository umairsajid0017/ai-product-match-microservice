from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Qdrant (Local Mode)
    qdrant_path: str = "qdrant_data"
    qdrant_collection: str = "products"

    # Image Storage
    image_base_path: str = "../orig_images"

    # Model
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"

    # Search
    default_top_k: int = 10
    similarity_threshold: float = 0.70

    # Security
    internal_api_key: str = ""
    laravel_callback_url: str = "https://everystore.pk/backend/api/internal/ai-matching/callback"

    class Config:
        env_file = ".env"


settings = Settings()
