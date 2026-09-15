"""Integration test for the deterministic all-MCP evidence fallback."""

from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.mcp.client import VerifiedMCPReportBuilder


def test_verified_report_uses_all_structured_evidence() -> None:
    query = "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    route = IntentRouter().classify(query)

    report = VerifiedMCPReportBuilder().build(query, route)

    assert "EUR 570.64" in report
    assert "44.95%" in report
    assert "RULE-005" in report
    assert "NB-CRD-001" in report or "NB-RSK-001" in report
    assert report.endswith("END OF VERIFIED REPORT")
