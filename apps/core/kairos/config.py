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

    voice_url: str = Field("http://voice:8100", alias="KAIROS_VOICE_URL")
    voice_timeout_seconds: int = Field(180, alias="KAIROS_VOICE_TIMEOUT_SECONDS")

    allow_egress: bool = Field(False, alias="KAIROS_ALLOW_EGRESS")
    # local  = solo Ollama, pase lo que pase
    # cloud  = remoto con caida a Ollama si falla
    # auto   = cloud si hay clave y egress; si no, local
    provider_mode: str = Field("auto", alias="KAIROS_PROVIDER_MODE")
    cloud_model: str = Field("claude-sonnet-4-6", alias="KAIROS_CLOUD_MODEL")
    cloud_max_tokens: int = Field(4096, alias="KAIROS_CLOUD_MAX_TOKENS")
    search_enabled: bool = Field(True, alias="KAIROS_SEARCH_ENABLED")
    search_results: int = Field(5, alias="KAIROS_SEARCH_RESULTS")
    search_region: str = Field("es-es", alias="KAIROS_SEARCH_REGION")
    timezone: str = Field("Europe/Madrid", alias="KAIROS_TIMEZONE")
    # El puente corre en Windows, fuera de Docker. host.docker.internal es
    # como Docker Desktop expone la maquina anfitriona al contenedor.
    bridge_url: str = Field("http://host.docker.internal:8200", alias="KAIROS_BRIDGE_URL")
    bridge_token: str = Field("", alias="KAIROS_BRIDGE_TOKEN")
    bridge_enabled: bool = Field(False, alias="KAIROS_BRIDGE_ENABLED")
    forge_url: str = Field("http://forge:8300", alias="KAIROS_FORGE_URL")
    forge_token: str = Field("", alias="KAIROS_FORGE_TOKEN")
    forge_enabled: bool = Field(False, alias="KAIROS_FORGE_ENABLED")
    smith_enabled: bool = Field(False, alias="KAIROS_SMITH_ENABLED")
    warden_url: str = Field("http://warden:8400", alias="KAIROS_WARDEN_URL")
    warden_token: str = Field("", alias="KAIROS_WARDEN_TOKEN")
    warden_enabled: bool = Field(False, alias="KAIROS_WARDEN_ENABLED")
    briefing_enabled: bool = Field(True, alias="KAIROS_BRIEFING_ENABLED")
    briefing_time: str = Field("15:30", alias="KAIROS_BRIEFING_TIME")
    briefing_weekends: bool = Field(True, alias="KAIROS_BRIEFING_WEEKENDS")
    briefing_city: str = Field("Madrid", alias="KAIROS_BRIEFING_CITY")
    watch_enabled: bool = Field(True, alias="KAIROS_WATCH_ENABLED")
    agenda_enabled: bool = Field(True, alias="KAIROS_AGENDA_ENABLED")
    curiosidad_enabled: bool = Field(True, alias="KAIROS_CURIOSIDAD_ENABLED")
    curiosidad_horas: int = Field(2, alias="KAIROS_CURIOSIDAD_HORAS")
    google_client_id: str = Field("", alias="KAIROS_GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", alias="KAIROS_GOOGLE_CLIENT_SECRET")
    watch_interval_minutes: int = Field(20, alias="KAIROS_WATCH_INTERVAL")
    attachments_dir: str = Field("/var/lib/kairos/attachments", alias="KAIROS_ATTACHMENTS_DIR")
    # Nombres adicionales por los que se puede llegar al nucleo, separados por
    # comas. Se usa para el acceso desde el movil por red privada.
    extra_hosts_raw: str = Field("", alias="KAIROS_EXTRA_HOSTS")
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")

    memory_top_k: int = Field(6, alias="KAIROS_MEMORY_TOP_K")
    memory_min_similarity: float = Field(0.55, alias="KAIROS_MEMORY_MIN_SIMILARITY")
    # >= duplicate: ya lo sabemos, no se guarda.
    # >= supersede: mismo tema con dato nuevo, el viejo pasa a superseded.
    memory_duplicate_threshold: float = Field(0.95, alias="KAIROS_MEMORY_DUPLICATE_THRESHOLD")
    memory_supersede_threshold: float = Field(0.82, alias="KAIROS_MEMORY_SUPERSEDE_THRESHOLD")

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
    def extra_hosts(self) -> list[str]:
        return [h.strip() for h in self.extra_hosts_raw.split(",") if h.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
