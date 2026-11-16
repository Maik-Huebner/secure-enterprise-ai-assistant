"""Typed runtime settings for local-first model and application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from platformdirs import user_state_path
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings without checked-in secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://localhost:11434"
    ollama_fast_model: str = Field(
        default="qwen3.5:9b",
        min_length=1,
        validation_alias=AliasChoices("OLLAMA_FAST_MODEL", "OLLAMA_MODEL"),
    )
    ollama_complex_model: str = Field(default="mistral-small3.2:24b", min_length=1)
    full_assessment_mode: Literal["verified_mcp", "agentic"] = "verified_mcp"
    ollama_request_timeout_seconds: int = Field(default=180, ge=15, le=900)
    # Embeddings: "ollama" for real use; "hashing" only for fast tests and offline baselines.
    embedding_backend: Literal["ollama", "sentence_transformers", "hashing"] = "ollama"
    embedding_model: str = "qwen3-embedding:0.6b"
    router_mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    embedding_timeout_seconds: int = Field(default=120, ge=5, le=900)
    # Optional override for the persistent index folder; default is <runtime_dir>/index.
    index_dir: Path | None = None
    app_env: str = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    llm_temperature: float = Field(default=0.1, ge=0, le=2)
    llm_max_tokens: int = Field(default=4096, ge=512, le=32768)
    ollama_think: bool = False
    agent_max_execution_seconds: int = Field(default=90, ge=15, le=600)
    mcp_request_timeout_seconds: int = Field(default=30, ge=5, le=300)
    runtime_dir: Path = Field(
        default_factory=lambda: user_state_path("secure-enterprise-ai-assistant")
    )
    ui_server_name: str = "127.0.0.1"
    ui_server_port: int = Field(default=7860, ge=1024, le=65535)

    # API and security (v1.3). JWT_SECRET has no default on purpose: no secret, no API.
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_base_url: str = "http://127.0.0.1:8000"
    api_docs_enabled: bool = True
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "novabank-assistant"
    jwt_audience: str = "novabank-api"
    jwt_ttl_minutes: int = Field(default=15, ge=1, le=120)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    login_rate_limit_per_minute: int = Field(default=5, ge=1, le=100)
    chat_rate_limit_per_minute: int = Field(default=20, ge=1, le=600)
    api_rate_limit_per_minute: int = Field(default=120, ge=1, le=6000)
    hsts_enabled: bool = False
    users_file: Path | None = None
    audit_log: Path | None = None

    @property
    def resolved_index_dir(self) -> Path:
        return self.index_dir or self.runtime_dir / "index"

    @property
    def resolved_users_file(self) -> Path:
        return self.users_file or self.runtime_dir / "security" / "users.json"

    @property
    def resolved_audit_log(self) -> Path:
        return self.audit_log or self.runtime_dir / "audit" / "audit.jsonl"


@lru_cache
def get_settings() -> Settings:
    """Return a process-local immutable-by-convention settings instance."""
    return Settings()
