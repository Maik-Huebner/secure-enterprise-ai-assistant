"""CrewAI Flow and deterministic routing with lazy optional-runtime imports."""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "IntentRouter":
        from secure_enterprise_ai_assistant.flows.router import IntentRouter

        return IntentRouter
    if name == "NovaBankAssistantFlow":
        from secure_enterprise_ai_assistant.flows.assistant import NovaBankAssistantFlow

        return NovaBankAssistantFlow
    raise AttributeError(name)


__all__ = ["IntentRouter", "NovaBankAssistantFlow"]
