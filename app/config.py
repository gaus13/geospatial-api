"""Application configuration loaded from environment variables."""

# What this file does:
# This will load validated settings such as database URLs, upload directory,
# and maximum upload size from environment variables.
#
# Why it is needed:
# Configuration must stay outside business logic so local, test, and Docker
# environments can use different values safely.

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    test_database_url: str
    max_upload_mb: int = 50
    upload_dir: Path = Path("uploads")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()


