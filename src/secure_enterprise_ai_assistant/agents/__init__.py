"""CrewAI agents and deterministic model routing with lazy runtime imports."""

from typing import Any


def __getattr__(name: str) -> Any:
    if name in {"AgentFactory", "CrewOrchestrator"}:
        from secure_enterprise_ai_assistant.agents.factory import AgentFactory, CrewOrchestrator

        return {"AgentFactory": AgentFactory, "CrewOrchestrator": CrewOrchestrator}[name]
    if name in {"ComplexityClass", "ModelProfile", "ModelRouter", "ModelSelection"}:
        from secure_enterprise_ai_assistant.agents.model_router import (
            ComplexityClass,
            ModelProfile,
            ModelRouter,
            ModelSelection,
        )

        return {
            "ComplexityClass": ComplexityClass,
            "ModelProfile": ModelProfile,
            "ModelRouter": ModelRouter,
            "ModelSelection": ModelSelection,
        }[name]
    raise AttributeError(name)


__all__ = [
    "AgentFactory",
    "ComplexityClass",
    "CrewOrchestrator",
    "ModelProfile",
    "ModelRouter",
    "ModelSelection",
]
