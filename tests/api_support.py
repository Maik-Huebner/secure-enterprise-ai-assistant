"""Shared test setup: a real API app with test users, hashing search and a stub workflow."""

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

from secure_enterprise_ai_assistant.api.app import ApiContext, FlowOutcome, FlowRunner, create_app
from secure_enterprise_ai_assistant.core.settings import Settings
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent, TraceEvent
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


def stub_flow(message: str, principal: Principal, access_token: str) -> FlowOutcome:
    """Deterministic workflow stand-in that respects the decision-brief permission."""
    del access_token
    route = IntentRouter().classify(message)
    if route.intent == QueryIntent.FULL_ASSESSMENT:
        offline_tools().access_policy.require_decision_brief(principal)
    trace = [
        TraceEvent(event="request_received", detail="Anfrage empfangen"),
        TraceEvent(event="intent_classified", detail=route.intent.value),
        TraceEvent(event="model_selected", detail="qwen3.5:9b"),
        TraceEvent(event="model_profile", detail="fast_local"),
        TraceEvent(event="execution_mode", detail="crewai"),
    ]
    return FlowOutcome(
        answer=f"Antwort mit Quelle NB-DOC-001 für {principal.username}", route=route, trace=trace
    )


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
    tmp_path: Path, flow_runner: FlowRunner = stub_flow, **overrides: object
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
        flow_runner=flow_runner,
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
