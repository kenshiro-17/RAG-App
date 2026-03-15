from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "RAG SaaS API"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/rag_app"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    auth_disabled: bool = True
    auth_default_email: str = "demo@local.dev"
    auth_default_workspace_name: str = "Demo Workspace"

    openai_api_key: str = ""
    openai_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str = "openai"
    embedding_dimensions: int = 1536
    response_model: str = "gpt-4.1-mini"

    storage_backend: str = "local"
    local_storage_path: str = "./data/storage"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    chunk_tokens: int = 450
    overlap_tokens: int = 80
    embedding_batch_size: int = 64
    retrieval_top_k: int = 8
    retrieval_vector_weight: float = 0.65
    retrieval_keyword_weight: float = 0.35
    retrieval_keyword_language: str = "english"

    rate_limit_capacity: int = 25
    rate_limit_refill_per_sec: float = 0.5

    sentry_dsn: str | None = None

    @model_validator(mode="after")
    def validate_retrieval_weights(self) -> "Settings":
        total = self.retrieval_vector_weight + self.retrieval_keyword_weight
        if total <= 0:
            raise ValueError("retrieval weights must sum to > 0")
        self.retrieval_vector_weight = self.retrieval_vector_weight / total
        self.retrieval_keyword_weight = self.retrieval_keyword_weight / total
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):  # type: ignore[no-untyped-def]
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return value
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
