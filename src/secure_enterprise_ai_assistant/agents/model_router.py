"""Deterministic local-model selection for routed NovaBank workflows."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from secure_enterprise_ai_assistant.core.settings import Settings, get_settings
from secure_enterprise_ai_assistant.models.domain import DomainModel
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent, RouteDecision


class ModelProfile(StrEnum):
    """Logical local-model profiles independent of concrete model identifiers."""

    FAST_LOCAL = "fast_local"
    COMPLEX_AGENTIC = "complex_agentic"


class ComplexityClass(StrEnum):
    """Workflow complexity used as an auditable routing attribute."""

    SIMPLE = "simple"
    COMPLEX = "complex"


class ModelSelection(DomainModel):
    """Auditable model choice made before a CrewAI workflow starts."""

    model: str = Field(min_length=1)
    profile: ModelProfile
    reason: str = Field(min_length=1)
    complexity_class: ComplexityClass


SIMPLE_REASONS: dict[QueryIntent, str] = {
    QueryIntent.KNOWLEDGE: "simple knowledge workflow",
    QueryIntent.CUSTOMER_CASE: "simple customer-case workflow",
    QueryIntent.FINANCIAL_ANALYSIS: "simple financial-analysis workflow",
    QueryIntent.COMPLIANCE_CHECK: "simple compliance workflow",
}
COMPLEX_INTENTS = frozenset({QueryIntent.FULL_ASSESSMENT})


class ModelRouter:
    """Select a configured Ollama profile from a deterministic route decision."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def select(self, route: RouteDecision) -> ModelSelection:
        """Return one stable model choice without invoking an LLM."""
        if route.intent in COMPLEX_INTENTS:
            return ModelSelection(
                model=self.settings.ollama_complex_model,
                profile=ModelProfile.COMPLEX_AGENTIC,
                reason="full multi-agent assessment requires robust tool calling",
                complexity_class=ComplexityClass.COMPLEX,
            )
        return ModelSelection(
            model=self.settings.ollama_fast_model,
            profile=ModelProfile.FAST_LOCAL,
            reason=SIMPLE_REASONS.get(
                route.intent,
                "simple or unrecognized workflow defaults to the fast local model",
            ),
            complexity_class=ComplexityClass.SIMPLE,
        )
