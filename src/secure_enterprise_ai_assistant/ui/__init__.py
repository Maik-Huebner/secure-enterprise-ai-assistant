"""Gradio application for the Secure Enterprise AI Assistant."""

from typing import Any


def build_app(*args: Any, **kwargs: Any) -> Any:
    """Lazily import the UI so module execution does not preload it."""
    from secure_enterprise_ai_assistant.ui.app import build_app as _build_app

    return _build_app(*args, **kwargs)


__all__ = ["build_app"]
