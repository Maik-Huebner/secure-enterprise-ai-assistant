"""NovaBank Model Context Protocol server and tool contracts."""

from typing import Any


def create_mcp_server(*args: Any, **kwargs: Any) -> Any:
    """Lazily import the server so ``python -m`` does not preload its module."""
    from secure_enterprise_ai_assistant.mcp.server import create_mcp_server as _create

    return _create(*args, **kwargs)


__all__ = ["create_mcp_server"]
