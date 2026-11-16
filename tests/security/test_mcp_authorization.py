"""The MCP tools enforce authorization themselves, also when called directly over stdio."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from secure_enterprise_ai_assistant.mcp.environment import server_environment
from secure_enterprise_ai_assistant.mcp.server import ACCESS_TOKEN_VARIABLE, create_mcp_server
from secure_enterprise_ai_assistant.security import AccessDeniedError, Principal
from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError
from tests.api_support import offline_tools
from tests.conftest import CASE_WORKER_NORD, REVIEWER, token_for


def test_tool_service_requires_rights_for_every_call() -> None:
    tools = offline_tools()

    with pytest.raises(CaseNotFoundError):
        tools.get_customer_case("CASE-00030", principal=CASE_WORKER_NORD)
    with pytest.raises(CaseNotFoundError):
        tools.analyze_financial_case("CASE-00001", principal=Principal.anonymous())
    with pytest.raises(AccessDeniedError):
        tools.search_internal_knowledge("Welche Unterlagen?", principal=Principal.anonymous())
    assert tools.get_customer_case("CASE-00030", principal=REVIEWER).case.case_id == "CASE-00030"


def test_in_process_mcp_server_uses_the_resolved_principal() -> None:
    server = create_mcp_server(offline_tools(), principal_provider=lambda: CASE_WORKER_NORD)

    async def call(name: str, arguments: dict[str, Any]) -> Any:
        return await server.call_tool(name, arguments)

    assert asyncio.run(call("get_customer_case", {"case_id": "CASE-00001"}))
    with pytest.raises(Exception, match="Unbekannte synthetische Fall-ID"):
        asyncio.run(call("get_customer_case", {"case_id": "CASE-00030"}))


async def _stdio_calls(token: str | None) -> dict[str, bool]:
    extra = {ACCESS_TOKEN_VARIABLE: token} if token else None
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "secure_enterprise_ai_assistant.mcp.server"],
        env=server_environment(extra),
    )
    results: dict[str, bool] = {}
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for label, name, arguments in (
                ("own_case", "get_customer_case", {"case_id": "CASE-00001"}),
                ("foreign_case", "get_customer_case", {"case_id": "CASE-00030"}),
                (
                    "search",
                    "search_internal_knowledge",
                    {"question": "Welche Unterlagen braucht ein Kredit?"},
                ),
            ):
                result = await session.call_tool(name, arguments)
                results[label] = not result.is_error
    return results


def test_stdio_mcp_server_enforces_the_token_of_the_caller() -> None:
    worker = asyncio.run(_stdio_calls(token_for(CASE_WORKER_NORD)))
    anonymous = asyncio.run(_stdio_calls(None))
    forged = asyncio.run(_stdio_calls("eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9."))

    assert worker == {"own_case": True, "foreign_case": False, "search": True}
    assert anonymous == {"own_case": False, "foreign_case": False, "search": False}
    assert forged == anonymous
