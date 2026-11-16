"""Shared test setup: a real API app with test users, hashing search and a test answer model."""

from __future__ import annotations

import warnings
from functools import cache
from pathlib import Path

from fastapi import FastAPI

with warnings.catch_warnings():
    # Starlette 1.6 prefers httpx2 for its TestClient; httpx2 arrives with MCP 2.x (package 5).
    warnings.filterwarnings(
        "ignore", message="Using `httpx` with `starlette.testclient`", category=UserWarning
    )
    # Starlette's TestClient still imports a deprecated anyio alias (third-party).
    warnings.filterwarnings(
        "ignore", message="The anyio.abc.BlockingPortal alias", category=DeprecationWarning
    )
    from fastapi.testclient import TestClient

import re
from collections.abc import Callable
from typing import Any

from secure_enterprise_ai_assistant.api.app import ApiContext, create_app
from secure_enterprise_ai_assistant.core.settings import Settings
from secure_enterprise_ai_assistant.graph.assistant import AssistantService
from secure_enterprise_ai_assistant.graph.llm import AnswerModel
from secure_enterprise_ai_assistant.graph.reviews import ReviewStore
from secure_enterprise_ai_assistant.mcp.client import (
    EVIDENCE_KEYS,
    knowledge_requests,
    merge_knowledge,
)
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.orchestration import RouteDecision
from secure_enterprise_ai_assistant.rag.embeddings import HashingEmbedder
from secure_enterprise_ai_assistant.rag.service import KnowledgeService
from secure_enterprise_ai_assistant.security import Principal, Role
from secure_enterprise_ai_assistant.security.audit import AuditLog
from secure_enterprise_ai_assistant.security.tokens import TokenService
from secure_enterprise_ai_assistant.security.users import UserStore

TEST_SECRET = "test-only-signing-key-not-for-any-deployment-0123456789"
# Test-only passwords for synthetic users that exist only inside temporary test folders.
PASSWORDS = {
    "sb.nord": "Testpasswort-Nord-2026",
    "sb.sued": "Testpasswort-Sued-2026",
    "pruefer": "Testpasswort-Pruefer-2026",
    "admin": "Testpasswort-Admin-2026",
}


@cache
def offline_tools() -> MCPToolService:
    return MCPToolService.build(KnowledgeService.from_directory(embedder=HashingEmbedder()))


class GroundedTestModel:
    """Answers by restating the evidence block and citing the first policy: always grounded."""

    name = "test-model"

    def generate(self, system: str, user: str) -> str:
        del system
        block = user.split("<nachweise>", 1)[1].split("</nachweise>", 1)[0]
        citation = re.search(r'<richtlinie id="([^"]+)" abschnitt="([^"]+)"', block)
        text = re.sub(r"<[^>]+>", "", block).strip()
        cite = f" ({citation.group(1)}, Abschnitt {citation.group(2)})" if citation else ""
        return f"Antwort auf Grundlage der Nachweise{cite}:\n{text[:800]}"


class InventingTestModel:
    """Always invents a number and a document: must be caught by verification."""

    name = "inventing-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system: str, user: str) -> str:
        del system, user
        self.calls += 1
        return "Die monatliche Rate beträgt 999,99 EUR laut NB-XYZ-999, Abschnitt 1."


class InProcessCollector:
    """Test stand-in for McpEvidenceClient: same tool methods and authorization, no subprocess."""

    def __init__(self, access_token: str | None) -> None:
        from tests.conftest import token_for  # noqa: F401  (ensures the test secret is set)

        self._principal = Principal.anonymous()
        if access_token:
            service = TokenService(TEST_SECRET, "novabank-assistant", "novabank-api", 15)
            self._principal = service.verify(access_token)

    def collect(self, route: RouteDecision, query: str) -> dict[str, dict[str, Any]]:
        tools, principal = offline_tools(), self._principal
        evidence: dict[str, dict[str, Any]] = {}
        for tool in route.required_tools:
            if tool == "get_customer_case":
                result: Any = tools.get_customer_case(str(route.case_id), principal=principal)
            elif tool == "analyze_financial_case":
                result = tools.analyze_financial_case(str(route.case_id), principal=principal)
            elif tool == "check_compliance":
                result = tools.check_compliance(str(route.case_id), principal=principal)
            else:
                responses = [
                    tools.search_internal_knowledge(
                        arguments["question"],
                        principal=principal,
                        top_k=arguments["top_k"],
                        document_id=arguments.get("document_id"),
                    ).model_dump(mode="json")
                    for arguments in knowledge_requests(route, query, evidence)
                ]
                evidence["knowledge"] = merge_knowledge(responses)
                continue
            evidence[EVIDENCE_KEYS[tool]] = result.model_dump(mode="json")
        return evidence


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "jwt_secret": TEST_SECRET,
        "embedding_backend": "hashing",
        "ollama_base_url": "http://127.0.0.1:9",  # unreachable on purpose
        "login_rate_limit_per_minute": 5,
        "chat_rate_limit_per_minute": 20,
        "api_rate_limit_per_minute": 1000,
    }
    values.update(overrides)
    # model_validate ignores environment variables: tests do not depend on the local shell.
    return Settings.model_validate(values)


def make_context(
    tmp_path: Path,
    model_factory: Callable[[], AnswerModel] = GroundedTestModel,
    collector: Callable[[str | None], Any] = InProcessCollector,
    **overrides: object,
) -> ApiContext:
    settings = make_settings(**overrides)
    users = UserStore(tmp_path / "users.json")
    users.add(
        "sb.nord", PASSWORDS["sb.nord"], Role.CASE_WORKER, "Sachbearbeitung Nord", "team-nord"
    )
    users.add("sb.sued", PASSWORDS["sb.sued"], Role.CASE_WORKER, "Sachbearbeitung Süd", "team-sued")
    users.add("pruefer", PASSWORDS["pruefer"], Role.REVIEWER, "Prüfung")
    users.add("admin", PASSWORDS["admin"], Role.ADMIN, "Administration")
    tools = offline_tools()
    return ApiContext(
        settings=settings,
        tokens=TokenService(TEST_SECRET, settings.jwt_issuer, settings.jwt_audience, 15),
        users=users,
        policy=tools.access_policy,
        tools=tools,
        audit=AuditLog(tmp_path / "audit.jsonl"),
        assistant=AssistantService(
            model_factory=model_factory, collector=collector, settings=settings
        ),
        reviews=ReviewStore(tmp_path / "reviews.json"),
    )


def make_client(
    tmp_path: Path, raise_server_exceptions: bool = True, **kwargs: object
) -> tuple[TestClient, ApiContext, FastAPI]:
    """``raise_server_exceptions=False`` shows what a real client receives on a 500."""
    context = make_context(tmp_path, **kwargs)  # type: ignore[arg-type]
    app = create_app(context)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), context, app


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/v1/auth/token", json={"username": username, "password": PASSWORDS[username]}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
