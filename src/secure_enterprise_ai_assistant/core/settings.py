"""Typed runtime settings for local-first model and application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
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
    embedding_model: str = ""
    app_env: str = "development"
    log_level: str = "INFO"
    llm_temperature: float = Field(default=0.1, ge=0, le=2)
    llm_max_tokens: int = Field(default=4096, ge=512, le=32768)
    ollama_think: bool = False
    agent_max_execution_seconds: int = Field(default=90, ge=15, le=600)
    ui_server_name: str = "127.0.0.1"
    ui_server_port: int = Field(default=7860, ge=1024, le=65535)


@lru_cache
def get_settings() -> Settings:
    """Return a process-local immutable-by-convention settings instance."""
    return Settings()
