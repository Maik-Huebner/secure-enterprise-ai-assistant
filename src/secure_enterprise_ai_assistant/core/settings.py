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
    llm_max_tokens: int = Field(default=1024, ge=128, le=32768)
    llm_context_tokens: int = Field(default=8192, ge=2048, le=131072)
    llm_seed: int = 7
    # One answer plus one corrected retry before the verified fallback takes over.
    answer_max_attempts: int = Field(default=2, ge=1, le=4)
    ollama_think: bool = False
    mcp_request_timeout_seconds: int = Field(default=30, ge=5, le=300)
    # MCP transport (v1.5): a stdio subprocess per request, or a separate Streamable HTTP
    # server that verifies its own short-lived tokens (audience MCP_AUDIENCE).
    mcp_transport: Literal["stdio", "http"] = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8001, ge=1024, le=65535)
    mcp_server_url: str = "http://127.0.0.1:8001/mcp"
    mcp_audience: str = "novabank-mcp"
    mcp_token_ttl_minutes: int = Field(default=5, ge=1, le=30)
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

    # Observability (v1.6): Langfuse, off by default. Nothing is sent without both keys.
    langfuse_enabled: bool = False
    langfuse_base_url: str = "http://localhost:3000"
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_pseudonymize_users: bool = True
    # Assumed price per million tokens for the cost view; local models cost nothing.
    llm_price_input_per_million_tokens: float = Field(default=0.0, ge=0)
    llm_price_output_per_million_tokens: float = Field(default=0.0, ge=0)
    audit_log: Path | None = None

    @property
    def resolved_index_dir(self) -> Path:
        return self.index_dir or self.runtime_dir / "index"

    @property
    def graph_checkpoint_path(self) -> Path:
        return self.runtime_dir / "graph" / "checkpoints.sqlite"

    @property
    def review_index_path(self) -> Path:
        return self.runtime_dir / "graph" / "reviews.json"

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
