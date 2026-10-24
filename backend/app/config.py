
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL = (
    f"sqlite:///{(Path(__file__).resolve().parents[1] / 'dev.db').as_posix()}"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parents[1] / ".env",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias=AliasChoices("DATABASE_URL", "DATABASE_URL_UNPOOLED"),
    )
    VISION_MODEL: str = "google_genai:gemini-3.1-flash-lite"
    TEXT_MODEL: str = "google_genai:gemini-3.1-flash-lite"
    LLM_API_KEY: str = ""
    LLM_KWARGS: dict = {}
    STORAGE_DIR: str = "storage"
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = ""
    CRON_SECRET: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    TWILIO_MESSAGING_SERVICE_SID: str = ""
    PUBLIC_APP_URL: str = "https://health-copilot-eight.vercel.app"

    # S3-compatible medical document storage
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "curamind-medical-files"


settings = Settings()
