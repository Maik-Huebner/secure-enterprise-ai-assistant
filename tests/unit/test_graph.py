"""LangGraph workflow: grounding, verification, retry, fallback, approval and checkpoint safety."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from secure_enterprise_ai_assistant.graph.assistant import AssistantResult, AssistantService
from secure_enterprise_ai_assistant.graph.evidence_text import NO_ANSWER
from secure_enterprise_ai_assistant.graph.llm import AnswerModel
from secure_enterprise_ai_assistant.security import AccessDeniedError
from tests.api_support import GroundedTestModel, InProcessCollector, InventingTestModel
from tests.conftest import ADMIN, CASE_WORKER_NORD, REVIEWER, token_for


class CountingModel(GroundedTestModel):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system: str, user: str) -> str:
        self.calls += 1
        return super().generate(system, user)


def _service(model: AnswerModel, tmp_path: Path | None = None) -> AssistantService:
    if tmp_path is not None:
        return AssistantService.with_sqlite(
            tmp_path / "checkpoints.sqlite",
            model_factory=lambda: model,
            collector=InProcessCollector,
        )
    return AssistantService(model_factory=lambda: model, collector=InProcessCollector)


def _events(result: AssistantResult) -> list[str]:
    return [event.event for event in result.trace]


def test_grounded_answer_passes_verification_on_first_attempt() -> None:
    result = _service(GroundedTestModel()).run(
        "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?",
        REVIEWER,
        token_for(REVIEWER),
    )

    assert result.status == "completed"
    assert result.execution_mode == "llm_grounded"
    assert "NB-DOC-001" in result.answer
    assert "answer_retry" not in _events(result)


def test_invented_numbers_and_sources_trigger_retry_then_verified_fallback() -> None:
    model = InventingTestModel()
    result = _service(model).run(
        "Berechne die Kreditbelastung für CASE-00031.", REVIEWER, token_for(REVIEWER)
    )

    assert model.calls == 2  # first answer plus one corrected retry
    assert result.execution_mode == "verified_fallback"
    assert "999,99" not in result.answer and "NB-XYZ-999" not in result.answer
    assert "570,64 EUR" in result.answer
    assert {"answer_retry", "fallback_reason"} <= set(_events(result))


def test_no_relevant_passage_answers_without_calling_the_model() -> None:
    model = CountingModel()
    result = _service(model).run(
        "Wie repariere ich einen Schiffsdieselmotor?", REVIEWER, token_for(REVIEWER)
    )

    assert result.answer == NO_ANSWER
    assert result.execution_mode == "no_answer"
    assert model.calls == 0


def test_tools_run_with_the_callers_rights() -> None:
    from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError

    with pytest.raises(CaseNotFoundError):
        _service(GroundedTestModel()).run(
            "Zeige CASE-00030.", CASE_WORKER_NORD, token_for(CASE_WORKER_NORD)
        )


def test_decision_brief_pauses_for_a_second_person_and_resumes() -> None:
    service = _service(CountingModel())
    draft = service.run(
        "Erstelle eine Entscheidungsvorlage für CASE-00031.", REVIEWER, token_for(REVIEWER)
    )

    assert draft.status == "awaiting_approval"
    assert draft.execution_mode == "verified_mcp"
    assert "Entscheidungsvorlage – CASE-00031" in service.draft(draft.thread_id)

    with pytest.raises(AccessDeniedError, match="Vier-Augen-Prinzip"):
        service.resume(draft.thread_id, True, "", REVIEWER, token_for(REVIEWER))
    # The refused self-approval must not leak into the second person's decision.
    final = service.resume(draft.thread_id, False, "Unterlagen fehlen.", ADMIN, token_for(ADMIN))

    assert final.status == "rejected"
    assert "approval_refused" in _events(final)
    assert "**Abgelehnt** von admin" in final.answer
    assert "approval_decision" in _events(final)


def test_case_workers_cannot_start_a_decision_brief() -> None:
    with pytest.raises(AccessDeniedError):
        _service(GroundedTestModel()).run(
            "Erstelle eine Entscheidungsvorlage für CASE-00001.",
            CASE_WORKER_NORD,
            token_for(CASE_WORKER_NORD),
        )


def test_access_token_is_never_written_to_the_checkpoint(tmp_path) -> None:
    token = token_for(REVIEWER)
    service = _service(GroundedTestModel(), tmp_path)
    draft = service.run("Erstelle eine Entscheidungsvorlage für CASE-00031.", REVIEWER, token)
    service.resume(draft.thread_id, True, "ok", ADMIN, token_for(ADMIN))
    service.close()

    # sqlite3's own context manager only commits; closing() really closes the connection.
    with closing(sqlite3.connect(tmp_path / "checkpoints.sqlite")) as connection:
        dump = b"".join(
            bytes(value)
            if isinstance(value, bytes | bytearray | memoryview)
            else str(value).encode()
            for row in connection.execute("SELECT * FROM checkpoints")
            for value in row
        ) + b"".join(
            bytes(value)
            if isinstance(value, bytes | bytearray | memoryview)
            else str(value).encode()
            for row in connection.execute("SELECT * FROM writes")
            for value in row
        )

    assert dump, "checkpoints were written"
    assert token.encode() not in dump
    assert token.split(".")[2].encode() not in dump  # not even the signature part


def test_checkpoints_survive_a_service_restart(tmp_path) -> None:
    first = _service(GroundedTestModel(), tmp_path)
    draft = first.run(
        "Erstelle eine Entscheidungsvorlage für CASE-00031.", REVIEWER, token_for(REVIEWER)
    )

    first.close()
    restarted = _service(GroundedTestModel(), tmp_path)
    final = restarted.resume(draft.thread_id, True, "", ADMIN, token_for(ADMIN))
    restarted.close()

    assert final.status == "approved"
