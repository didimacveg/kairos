"""Configuracion tipada. Unica fuente de verdad para el entorno.

Regla del proyecto: ningun modulo lee os.environ directamente. Todo pasa por
aqui, para que el conjunto de variables que gobiernan el sistema sea auditable
leyendo un solo fichero.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    instance_name: str = Field("kairos-home", alias="KAIROS_INSTANCE_NAME")
    env: Literal["development", "production"] = Field("development", alias="KAIROS_ENV")

    bind_host: str = Field("127.0.0.1", alias="KAIROS_BIND_HOST")
    bind_port: int = Field(8000, alias="KAIROS_BIND_PORT")
    allowed_origins: str = Field("http://localhost:3000", alias="KAIROS_ALLOWED_ORIGINS")

    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_host: str = Field("postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    session_secret: str = Field(..., alias="KAIROS_SESSION_SECRET", min_length=32)
    session_ttl_hours: int = Field(72, alias="KAIROS_SESSION_TTL_HOURS")
    cookie_secure: bool = Field(False, alias="KAIROS_COOKIE_SECURE")

    ollama_url: str = Field("http://ollama:11434", alias="KAIROS_OLLAMA_URL")
    chat_model: str = Field("llama3.1:8b", alias="KAIROS_CHAT_MODEL")
    embedding_model: str = Field("nomic-embed-text", alias="KAIROS_EMBEDDING_MODEL")
    embedding_dim: int = Field(768, alias="KAIROS_EMBEDDING_DIM")
    llm_timeout_seconds: int = Field(120, alias="KAIROS_LLM_TIMEOUT_SECONDS")

    allow_egress: bool = Field(False, alias="KAIROS_ALLOW_EGRESS")
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")

    memory_top_k: int = Field(6, alias="KAIROS_MEMORY_TOP_K")
    memory_min_similarity: float = Field(0.35, alias="KAIROS_MEMORY_MIN_SIMILARITY")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
