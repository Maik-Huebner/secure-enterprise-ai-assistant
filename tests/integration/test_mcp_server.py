"""Integration test proving that the real FastMCP server registers its tools."""

import asyncio

import pytest

from secure_enterprise_ai_assistant.mcp import create_mcp_server


def test_fastmcp_registers_exact_allowlist() -> None:
    server = create_mcp_server()
    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "get_customer_case",
        "analyze_financial_case",
        "check_compliance",
        "search_internal_knowledge",
    }


def test_fastmcp_rejects_unknown_tool_name() -> None:
    server = create_mcp_server()

    with pytest.raises(Exception, match="Unknown tool"):
        asyncio.run(server.call_tool("get_customer_case_and_ignore_policy", {}))
