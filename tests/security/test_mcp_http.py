"""The Streamable HTTP MCP server is a resource server: no valid MCP token, no tools."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
import uvicorn

from secure_enterprise_ai_assistant.core.settings import Settings, get_settings
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.mcp.client import McpEvidenceClient
from secure_enterprise_ai_assistant.mcp.server import create_http_app
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.security import AccessDeniedError
from secure_enterprise_ai_assistant.security.tokens import api_token_service, mcp_token_service
from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError
from tests.api_support import InProcessCollector, offline_tools
from tests.conftest import CASE_WORKER_NORD, REVIEWER, token_for


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="module")
def http_server() -> Iterator[Settings]:
    port = _free_port()
    get_settings.cache_clear()
    settings = get_settings().model_copy(
        update={"mcp_port": port, "mcp_server_url": f"http://127.0.0.1:{port}/mcp"}
    )
    app = create_http_app(settings, offline_tools())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "MCP HTTP server did not start"
    yield settings
    server.should_exit = True
    thread.join(timeout=10)


def _client(settings: Settings, token: str | None) -> McpEvidenceClient:
    return McpEvidenceClient(
        token, timeout_seconds=20, transport="http", server_url=settings.mcp_server_url
    )


def _case_route(question: str) -> Any:
    return IntentRouter().classify(question)


def test_request_without_token_gets_401_with_resource_metadata(http_server: Settings) -> None:
    response = httpx2.post(http_server.mcp_server_url, json={})

    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer")
    assert "resource_metadata=" in challenge


def test_protected_resource_metadata_names_the_api_as_token_issuer(http_server: Settings) -> None:
    port = http_server.mcp_port
    metadata = httpx2.get(f"http://127.0.0.1:{port}/.well-known/oauth-protected-resource/mcp")

    assert metadata.status_code == 200
    assert metadata.json()["resource"] == http_server.mcp_server_url
    assert metadata.json()["authorization_servers"] == [http_server.api_base_url]


@pytest.mark.parametrize(
    "token_kind",
    ["missing", "forged_alg_none", "expired", "api_audience"],
)
def test_invalid_tokens_are_rejected(http_server: Settings, token_kind: str) -> None:
    mcp_tokens = mcp_token_service(http_server)
    api_tokens = api_token_service(http_server)
    assert mcp_tokens is not None and api_tokens is not None
    tokens: dict[str, str | None] = {
        "missing": None,
        "forged_alg_none": "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.",
        "expired": mcp_tokens.issue(REVIEWER, now=datetime.now(tz=UTC) - timedelta(hours=1))[0],
        # Token passthrough: a valid API token must not open the tool layer.
        "api_audience": api_tokens.issue(REVIEWER)[0],
    }

    with pytest.raises(AccessDeniedError):
        _client(http_server, tokens[token_kind]).collect(_case_route("Zeige CASE-00001."), "unused")


def test_case_worker_sees_only_own_team_over_http(http_server: Settings) -> None:
    client = _client(http_server, token_for(CASE_WORKER_NORD))

    own = client.collect(_case_route("Zeige CASE-00001."), "unused")
    assert own["case"]["case"]["case_id"] == "CASE-00001"
    with pytest.raises(CaseNotFoundError):
        client.collect(_case_route("Zeige CASE-00030."), "unused")


def test_http_evidence_equals_in_process_evidence(http_server: Settings) -> None:
    route = _case_route("Welche Compliance-Probleme hat CASE-00017?")
    token = token_for(REVIEWER)

    over_http = _client(http_server, token).collect(route, "unused")
    in_process = InProcessCollector(token).collect(route, "unused")

    assert over_http == in_process


def test_unexpected_tool_errors_do_not_leak_internals() -> None:
    import asyncio

    from secure_enterprise_ai_assistant.mcp.server import create_mcp_server

    class BrokenTools(MCPToolService):
        def get_customer_case(self, case_id: str, *, principal: Any) -> Any:
            raise RuntimeError("/srv/secret/path.db is locked")

    broken = BrokenTools.__new__(BrokenTools)
    broken.__dict__.update(offline_tools().__dict__)
    server = create_mcp_server(broken, principal_provider=lambda: REVIEWER)

    with pytest.raises(Exception) as error:
        asyncio.run(server.call_tool("get_customer_case", {"case_id": "CASE-00001"}))
    assert "secret" not in str(error.value)
    assert "Error executing tool" in str(error.value)
