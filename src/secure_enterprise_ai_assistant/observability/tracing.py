"""Langfuse tracing for the LangGraph workflow.

Off by default. It is switched on only with ``LANGFUSE_ENABLED=true`` *and* both project keys;
otherwise no client is created and nothing leaves the machine. When on, every workflow run is
one trace: graph nodes as spans, the answer model as a generation with prompt, answer and token
usage, user (pseudonymized) and thread as session. Cost is computed by Langfuse from a model
definition with a configurable price (``novabank-langfuse setup``); local models cost nothing,
so the default price is 0.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import TYPE_CHECKING, Any

from secure_enterprise_ai_assistant import __version__
from secure_enterprise_ai_assistant.core.logs import get_logger
from secure_enterprise_ai_assistant.core.settings import Settings

if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.runnables import RunnableConfig
    from langfuse import Langfuse
    from opentelemetry.sdk.trace.export import SpanExporter

logger = get_logger(__name__)

# Anything that looks like a JWT is removed before export (defense in depth: tokens are run
# context and should never be part of traced state in the first place).
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*")
TOKEN_PLACEHOLDER = "[TOKEN ENTFERNT]"


def mask_secrets(*, data: Any, **_: Any) -> Any:
    """Langfuse mask function: replace JWT-like strings in any traced value."""
    if isinstance(data, str):
        return JWT_PATTERN.sub(TOKEN_PLACEHOLDER, data)
    if isinstance(data, dict):
        return {key: mask_secrets(data=value) for key, value in data.items()}
    if isinstance(data, list | tuple):
        return [mask_secrets(data=value) for value in data]
    return data


class Tracing:
    """Thin wrapper; a disabled instance hands out no callbacks and never touches the network."""

    def __init__(self, settings: Settings, client: Langfuse | None = None) -> None:
        self._settings = settings
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def client(self) -> Langfuse | None:
        return self._client

    def user_id(self, username: str) -> str:
        """Pseudonymous, stable user ID (HMAC of the user name), or the name itself.

        The HMAC key is the application's JWT secret, which the Langfuse server never sees,
        so the trace store cannot map IDs back to names by trying known user names.
        """
        if not self._settings.langfuse_pseudonymize_users:
            return username
        key = self._settings.jwt_secret
        secret = key.get_secret_value().encode() if key is not None else b"novabank"
        return "u-" + hmac.new(secret, username.encode(), hashlib.sha256).hexdigest()[:16]

    def run_config(self, username: str, thread_id: str, operation: str) -> RunnableConfig:
        """Run config for one graph invocation; with tracing: callbacks and Langfuse metadata."""
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        if self._client is None:
            return config
        from langfuse.langchain import CallbackHandler

        handler: BaseCallbackHandler = CallbackHandler(
            public_key=self._settings.langfuse_public_key
        )
        return {
            **config,
            "callbacks": [handler],
            "run_name": f"novabank-{operation}",
            "metadata": {
                "langfuse_user_id": self.user_id(username),
                "langfuse_session_id": thread_id,
                "langfuse_tags": ["novabank", operation, self._settings.app_env],
            },
        }

    def flush(self) -> None:
        if self._client is not None:
            self._client.flush()

    def shutdown(self) -> None:
        if self._client is not None:
            self._client.shutdown()


def build_tracing(settings: Settings, span_exporter: SpanExporter | None = None) -> Tracing:
    """Create tracing from settings; ``span_exporter`` lets tests capture spans offline."""
    if not settings.langfuse_enabled:
        return Tracing(settings)
    if not settings.langfuse_public_key or settings.langfuse_secret_key is None:
        logger.warning("langfuse_disabled_missing_keys")
        return Tracing(settings)
    from langfuse import Langfuse

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
        environment=settings.app_env,
        release=__version__,
        mask=mask_secrets,
        span_exporter=span_exporter,
    )
    logger.info("langfuse_enabled", extra={"base_url": settings.langfuse_base_url})
    return Tracing(settings, client)
