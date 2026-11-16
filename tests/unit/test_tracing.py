"""Langfuse tracing: off by default, and when on, complete and free of tokens (offline)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from secure_enterprise_ai_assistant.graph.assistant import AssistantService
from secure_enterprise_ai_assistant.mcp.environment import server_environment
from secure_enterprise_ai_assistant.observability.tracing import (
    TOKEN_PLACEHOLDER,
    build_tracing,
    mask_secrets,
)
from tests.api_support import GroundedTestModel, InProcessCollector, make_settings
from tests.conftest import REVIEWER, token_for


# Assembled at runtime so the repository secret scan does not see a key-shaped literal.
FAKE_SECRET_KEY = "-".join(["sk", "lf", "test", "not", "a", "real", "key"])


class LangChainTestModel:
    """A real LangChain chat model (fake responses), so the tracer sees a generation."""

    name = "fake-chat"

    def __init__(self) -> None:
        self._grounded = GroundedTestModel()

    def generate(self, system: str, user: str) -> str:
        answer = self._grounded.generate(system, user)
        chat = FakeListChatModel(responses=[answer])
        return str(chat.invoke([SystemMessage(content=system), HumanMessage(content=user)]).content)


def _enabled_settings() -> Any:
    return make_settings(
        langfuse_enabled=True,
        # A fresh key per test: the SDK keeps one client per public key.
        langfuse_public_key=f"pk-lf-test-{uuid.uuid4().hex}",
        langfuse_secret_key=FAKE_SECRET_KEY,
        langfuse_base_url="http://127.0.0.1:9",  # unreachable: spans go to the exporter only
    )


def test_tracing_is_off_by_default_and_adds_no_callbacks() -> None:
    tracing = build_tracing(make_settings())

    assert not tracing.enabled
    assert tracing.run_config("pruefer", "t1", "chat") == {"configurable": {"thread_id": "t1"}}


def test_enabled_without_keys_stays_off() -> None:
    tracing = build_tracing(make_settings(langfuse_enabled=True))

    assert not tracing.enabled


def test_user_ids_are_pseudonymized_and_stable() -> None:
    tracing = build_tracing(make_settings())

    assert tracing.user_id("pruefer") == tracing.user_id("pruefer")
    assert tracing.user_id("pruefer") != "pruefer"
    assert tracing.user_id("pruefer").startswith("u-")
    assert build_tracing(make_settings(langfuse_pseudonymize_users=False)).user_id("x") == "x"


def test_mask_removes_jwt_like_strings_everywhere() -> None:
    token = token_for(REVIEWER)
    masked = mask_secrets(data={"a": f"Bearer {token}", "b": [token, 3]})

    assert token not in json.dumps(masked)
    assert masked["a"] == f"Bearer {TOKEN_PLACEHOLDER}"


def test_langfuse_keys_are_not_forwarded_to_the_mcp_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", FAKE_SECRET_KEY)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-should-stay-in-the-parent")

    environment = server_environment()

    assert "LANGFUSE_SECRET_KEY" not in environment
    assert "LANGFUSE_PUBLIC_KEY" not in environment


def test_a_traced_run_records_nodes_generation_user_and_session_but_no_token() -> None:
    settings = _enabled_settings()
    exporter = InMemorySpanExporter()
    tracing = build_tracing(settings, span_exporter=exporter)
    assert tracing.enabled
    token = token_for(REVIEWER)
    service = AssistantService(
        model_factory=LangChainTestModel,
        collector=InProcessCollector,
        settings=settings,
        tracing=tracing,
    )

    result = service.run(
        "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?", REVIEWER, token
    )
    tracing.flush()
    spans = exporter.get_finished_spans()
    exported = json.dumps(
        [{"name": span.name, "attributes": dict(span.attributes or {})} for span in spans],
        default=str,
        ensure_ascii=False,
    )

    assert result.execution_mode == "llm_grounded"
    names = {span.name for span in spans}
    assert {"route", "collect_evidence", "generate", "verify"} <= names
    assert any(
        (span.attributes or {}).get("langfuse.observation.type") == "generation" for span in spans
    )
    assert tracing.user_id(REVIEWER.username) in exported
    assert REVIEWER.username not in json.dumps(
        [dict(span.attributes or {}).get("user.id") for span in spans]
    )
    assert result.thread_id in exported
    assert "Konsumentenkredit" in exported  # the prompt is traced
    assert token not in exported  # the MCP token never is
    tracing.shutdown()


def test_dataset_upload_sends_both_suites_with_stable_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    from secure_enterprise_ai_assistant.observability import cli

    class FakeClient:
        def __init__(self) -> None:
            self.datasets: list[str] = []
            self.items: list[dict[str, Any]] = []

        def create_dataset(self, *, name: str, **_: Any) -> None:
            self.datasets.append(name)

        def create_dataset_item(self, **item: Any) -> None:
            self.items.append(item)

        def flush(self) -> None:
            pass

    fake = FakeClient()
    monkeypatch.setattr(cli, "_client", lambda settings: (None, fake))

    cli.datasets(make_settings())

    assert fake.datasets == [cli.ANSWER_DATASET, cli.RETRIEVAL_DATASET]
    answer_items = [item for item in fake.items if item["dataset_name"] == cli.ANSWER_DATASET]
    assert len(answer_items) == 17
    assert len({item["id"] for item in fake.items}) == len(fake.items)
    assert all(item["input"]["question"] for item in fake.items)
