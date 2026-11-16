"""Unit tests for defensive MCP tool behavior."""

import pytest

from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from tests.conftest import REVIEWER


@pytest.fixture(scope="module")
def tools() -> MCPToolService:
    return MCPToolService.build_default()


def test_case_and_financial_tools_return_structured_models(tools: MCPToolService) -> None:
    case_result = tools.get_customer_case("case-00001", principal=REVIEWER)
    financial_result = tools.analyze_financial_case("CASE-00001", principal=REVIEWER)

    assert case_result.case.case_id == "CASE-00001"
    assert financial_result.case_id == "CASE-00001"
    assert financial_result.metrics.monthly_payment_eur > 0


def test_compliance_tool_reports_demo_problem(tools: MCPToolService) -> None:
    result = tools.check_compliance("CASE-00017", principal=REVIEWER)

    assert any(not item.passed for item in result.findings)


def test_tool_boundary_rejects_invalid_inputs(tools: MCPToolService) -> None:
    with pytest.raises(ValueError, match="fünf Ziffern"):
        tools.get_customer_case("../CASE-00001", principal=REVIEWER)
    with pytest.raises(ValueError, match="zwischen 1 und 10"):
        tools.search_internal_knowledge("gültige Frage", principal=REVIEWER, top_k=100)
    with pytest.raises(ValueError, match="zwischen 1 und 10"):
        tools.search_internal_knowledge("gültige Frage", principal=REVIEWER, top_k=True)
    with pytest.raises(ValueError, match="Filter document_id"):
        tools.search_internal_knowledge(
            "gültige Frage", principal=REVIEWER, document_id="../../secrets"
        )
    with pytest.raises(ValueError, match="unzulässige Zeichen"):
        tools.search_internal_knowledge("gültige Frage", principal=REVIEWER, owner="A" * 121)


def test_knowledge_tool_returns_sources(tools: MCPToolService) -> None:
    result = tools.search_internal_knowledge(
        "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?", principal=REVIEWER
    )

    assert result.out_of_scope is False
    assert result.results[0].chunk.document_id == "NB-DOC-001"


def test_mcp_subprocess_environment_forwards_settings_but_not_foreign_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from secure_enterprise_ai_assistant.mcp.environment import server_environment

    monkeypatch.setenv("EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-leak")

    environment = server_environment({"EXTRA": "1"})

    assert environment["EMBEDDING_BACKEND"] == "hashing"
    assert environment["OLLAMA_BASE_URL"] == "http://127.0.0.1:11434"
    assert environment["EXTRA"] == "1"
    assert "AWS_SECRET_ACCESS_KEY" not in environment
