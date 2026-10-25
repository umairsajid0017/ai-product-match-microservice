from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_INTERNAL_API_KEY_LENGTH = 16

PLACEHOLDER_INTERNAL_API_KEYS = {
    "change-me",
    "changeme",
    "change-me-to-a-strong-secret",
    "your-api-key",
    "placeholder",
    "test",
}


class SecurityConfigurationError(RuntimeError):
    """Raised when the service would start without usable authentication."""


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

    # URL image ingestion. Empty means every URL fetch is rejected.
    allowed_image_hosts: str = "cdn.everystore.pk"
    max_url_redirects: int = 3
    max_image_pixels: int = 40_000_000

    @property
    def allowed_image_host_set(self) -> set[str]:
        return {
            host.strip().lower().rstrip(".")
            for host in self.allowed_image_hosts.split(",")
            if host.strip()
        }


settings = Settings()


def validate_runtime_security() -> None:
    """Fail startup when protected routes would be reachable unauthenticated."""
    key = (settings.internal_api_key or "").strip()

    if not key:
        raise SecurityConfigurationError(
            "INTERNAL_API_KEY is not configured. The service refuses to start "
            "without authentication for its protected routes."
        )

    if len(key) < MIN_INTERNAL_API_KEY_LENGTH:
        raise SecurityConfigurationError(
            f"INTERNAL_API_KEY must be at least {MIN_INTERNAL_API_KEY_LENGTH} "
            "characters long."
        )

    if key.lower() in PLACEHOLDER_INTERNAL_API_KEYS:
        raise SecurityConfigurationError(
            "INTERNAL_API_KEY still holds a placeholder value."
        )
