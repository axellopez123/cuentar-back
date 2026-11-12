import json
from typing import Any, List, Optional, Union
from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Settings
    PROJECT_NAME: str = "Cuentar API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production-1234567890abcdef"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database Settings
    CUSTOM_DATABASE_URL: Optional[str] = Field(None, alias="DATABASE_URL")
    USE_SQLITE_DEV: bool = False

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "cuentar_db"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        url = self.CUSTOM_DATABASE_URL
        if url:
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        if self.USE_SQLITE_DEV:
            return "sqlite+aiosqlite:///./cuentar_dev.db"
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Storage & Uploads
    UPLOAD_DIR: str = "storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    ]

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        "https://cuentar.arwax.pro",
        "http://cuentar.arwax.pro",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        elif isinstance(v, (list, set, tuple)):
            return [str(origin).strip() for origin in v]
        return []


settings = Settings()

