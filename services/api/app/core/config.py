from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me"

    DATABASE_URL: str = "postgresql+asyncpg://kops:kops@db:5432/kops"
    REDIS_URL: str = "redis://cache:6379/0"
    CHROMA_URL: str = "http://vector:8000"
    # Comma-separated. pydantic-settings JSON-decodes complex types from env
    # before validators run, so we keep this as a plain str and parse on read.
    CORS_ORIGINS: str = "http://localhost:7000"

    JWT_SECRET: str = "change-me-jwt"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MIN: int = 60
    REFRESH_TOKEN_TTL_DAYS: int = 14
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str | None = None

    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-pro"
    EMBEDDING_MODEL: str = "text-embedding-004"
    EMBEDDING_DIM: int = 768

    MAX_UPLOAD_MB: int = 25
    RATE_LIMIT_PER_MIN: int = 60
    QUERY_RATE_LIMIT_PER_MIN: int = 20
    LOGIN_RATE_LIMIT_PER_15MIN: int = 5

    INSIGHT_COORDINATOR_CRON: str = "*/30 * * * *"
    INSIGHT_NIGHTLY_AUDIT_CRON: str = "0 3 * * *"

    CHROMA_COLLECTION: str = "kops_chunks"

    # Shared upload dir — must be a path that both the api and worker
    # containers can read/write. In docker-compose this is bind-mounted as
    # a named volume; locally it defaults to ./uploads under the cwd.
    UPLOAD_ROOT: str = "uploads"

    @field_validator("COOKIE_DOMAIN", mode="before")
    @classmethod
    def empty_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
