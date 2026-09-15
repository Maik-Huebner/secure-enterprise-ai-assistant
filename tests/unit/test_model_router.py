"""Deterministic dual-model routing tests."""

from types import SimpleNamespace

import pytest

from secure_enterprise_ai_assistant.agents.model_router import (
    ComplexityClass,
    ModelProfile,
    ModelRouter,
)
from secure_enterprise_ai_assistant.core.settings import Settings
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent

FAST_MODEL = "fast-test-model"
COMPLEX_MODEL = "complex-test-model"


@pytest.fixture
def model_router() -> ModelRouter:
    return ModelRouter(
        Settings(
            ollama_fast_model=FAST_MODEL,
            ollama_complex_model=COMPLEX_MODEL,
        )
    )


@pytest.mark.parametrize(
    "query",
    [
        "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?",
        "Zeige CASE-00001.",
        "Berechne die Kreditbelastung für CASE-00001.",
        "Welche Compliance-Probleme hat CASE-00017?",
    ],
)
def test_simple_intents_select_qwen_profile(
    model_router: ModelRouter,
    query: str,
) -> None:
    route = IntentRouter().classify(query)

    selection = model_router.select(route)

    assert selection.model == FAST_MODEL
    assert selection.profile == ModelProfile.FAST_LOCAL
    assert selection.complexity_class == ComplexityClass.SIMPLE


def test_full_assessment_selects_mistral_profile(model_router: ModelRouter) -> None:
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )

    selection = model_router.select(route)

    assert route.intent == QueryIntent.FULL_ASSESSMENT
    assert selection.model == COMPLEX_MODEL
    assert selection.profile == ModelProfile.COMPLEX_AGENTIC
    assert selection.complexity_class == ComplexityClass.COMPLEX


def test_model_routing_is_deterministic(model_router: ModelRouter) -> None:
    route = IntentRouter().classify("Berechne die Kreditbelastung für CASE-00031.")

    assert model_router.select(route) == model_router.select(route)


def test_unknown_future_simple_intent_defaults_to_fast_model(
    model_router: ModelRouter,
) -> None:
    future_route = SimpleNamespace(intent="future_simple_intent")

    selection = model_router.select(future_route)  # type: ignore[arg-type]

    assert selection.model == FAST_MODEL
    assert selection.profile == ModelProfile.FAST_LOCAL


def test_model_selection_contains_auditable_reason(model_router: ModelRouter) -> None:
    simple = model_router.select(
        IntentRouter().classify("Berechne die Kreditbelastung für CASE-00031.")
    )
    complex_selection = model_router.select(
        IntentRouter().classify(
            "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
        )
    )

    assert simple.reason == "simple financial-analysis workflow"
    assert "multi-agent assessment" in complex_selection.reason


def test_legacy_ollama_model_environment_variable_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OLLAMA_FAST_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "legacy-fast-model")

    settings = Settings(_env_file=None)

    assert settings.ollama_fast_model == "legacy-fast-model"
