"""Environment for MCP stdio subprocesses: application settings only, nothing else.

The MCP SDK starts stdio servers with a minimal environment (HOME, PATH, ...). Without help the
server would not see settings such as EMBEDDING_BACKEND or OLLAMA_BASE_URL. Passing the whole
parent environment would leak unrelated secrets, so only known setting names are forwarded.
"""

from __future__ import annotations

import os

from secure_enterprise_ai_assistant.core.settings import Settings

_EXTRA_NAMES = frozenset(
    {
        "OLLAMA_MODEL",  # legacy alias of OLLAMA_FAST_MODEL
        "CREWAI_DISABLE_TELEMETRY",
        "CREWAI_TRACING_ENABLED",
        "CREWAI_STORAGE_DIR",
    }
)


def forwarded_names() -> frozenset[str]:
    """Upper-case environment variable names that belong to this application."""
    return frozenset(name.upper() for name in Settings.model_fields) | _EXTRA_NAMES


def server_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the allowlisted parent environment plus ``extra`` for an MCP subprocess."""
    names = forwarded_names()
    environment = {key: value for key, value in os.environ.items() if key.upper() in names}
    environment.update(extra or {})
    return environment
