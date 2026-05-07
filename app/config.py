from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "products"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

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

    class Config:
        env_file = ".env"


settings = Settings()
