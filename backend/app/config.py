
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parents[1] / ".env",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///dev.db"
    VISION_MODEL: str = "google_genai:gemini-3.1-flash-lite"
    TEXT_MODEL: str = "google_genai:gemini-3.1-flash-lite"
    LLM_API_KEY: str = ""
    LLM_KWARGS: dict = {}
    STORAGE_DIR: str = "storage"

    # S3-compatible medical document storage
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "curamind-medical-files"


settings = Settings()
