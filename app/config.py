from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Neon Postgres + pgvector
    database_url: str = ""

    # SQS (async embedding queue)
    sqs_queue_url: str = ""
    sqs_dlq_url: str = ""
    # On Lambda, runtime injects AWS_REGION; pydantic maps aws_region <-> AWS_REGION
    aws_region: str = "ap-south-1"

    # Optional S3 staging for multipart image uploads on embed
    s3_bucket: str = ""

    # Legacy local paths (optional; URL-based images preferred on Lambda)
    image_base_path: str = "../orig_images"

    # Model
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"

    # Search
    default_top_k: int = 10
    similarity_threshold: float = 0.70

    # Security
    internal_api_key: str = ""
    laravel_callback_url: str = (
        "https://backend.everystore.pk/api/internal/ai-matching/callback"
    )


settings = Settings()
