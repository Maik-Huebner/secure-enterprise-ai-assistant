"""Live tests against the real local stack (Ollama + embeddings + MCP stdio).

Deselected by default (marker ``live``); run with ``make test-live``. GitHub runners cannot run a
9B model sensibly, so these tests are local only. They check behavior, not exact wording.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest

from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.evaluation.answer_quality import fact_hits
from secure_enterprise_ai_assistant.graph.assistant import AssistantService
from secure_enterprise_ai_assistant.mcp.server import token_service_from_settings
from secure_enterprise_ai_assistant.security import Principal
from tests.conftest import CASE_WORKER_NORD, REVIEWER

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_service() -> Iterator[AssistantService]:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        httpx.get(f"{base_url}/api/tags", timeout=3).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"Ollama ist unter {base_url} nicht erreichbar.")
    previous = os.environ.get("EMBEDDING_BACKEND")
    os.environ["EMBEDDING_BACKEND"] = "ollama"  # the MCP subprocess inherits this
    get_settings.cache_clear()
    service = AssistantService()
    yield service
    service.close()
    os.environ["EMBEDDING_BACKEND"] = previous or "hashing"
    get_settings.cache_clear()


def _token(principal: Principal) -> str:
    tokens = token_service_from_settings()
    assert tokens is not None
    return tokens.issue(principal)[0]


def test_knowledge_answer_is_grounded_and_complete(live_service: AssistantService) -> None:
    result = live_service.run(
        "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?",
        REVIEWER,
        _token(REVIEWER),
    )

    assert result.execution_mode in {"llm_grounded", "verified_fallback"}
    assert all(fact_hits(result.answer, [["Ausweis"], ["Einkommensnachweis"], ["90 Tage"]]))
    assert "NB-DOC-001" in result.answer


def test_financial_numbers_come_from_the_tool(live_service: AssistantService) -> None:
    result = live_service.run(
        "Berechne die Kreditbelastung für CASE-00031.", REVIEWER, _token(REVIEWER)
    )

    assert "570,64" in result.answer
    assert "44,95" in result.answer


def test_unanswerable_question_is_declined_without_a_model_call(
    live_service: AssistantService,
) -> None:
    result = live_service.run(
        "Wie hoch ist der Dispozins für ein Girokonto?", REVIEWER, _token(REVIEWER)
    )

    assert result.execution_mode == "no_answer"
    assert "model_selected" not in [event.event for event in result.trace]


def test_foreign_team_case_stays_hidden(live_service: AssistantService) -> None:
    from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError

    with pytest.raises(CaseNotFoundError):
        live_service.run("Zeige CASE-00031.", CASE_WORKER_NORD, _token(CASE_WORKER_NORD))
