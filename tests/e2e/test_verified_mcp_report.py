"""Integration test for the deterministic all-MCP evidence fallback."""

from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.mcp.client import VerifiedMCPReportBuilder
from tests.conftest import REVIEWER, token_for


def test_verified_report_uses_all_structured_evidence() -> None:
    query = "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    route = IntentRouter().classify(query)

    report = VerifiedMCPReportBuilder(access_token=token_for(REVIEWER)).build(query, route)

    assert "Sofia Kern" in report
    assert "570,64 EUR" in report
    assert "28,41 %" in report
    assert "44,95 %" in report
    assert "5.488,40 EUR" in report
    assert "RULE-005" in report and "nicht bestanden" in report
    assert "**Empfehlung: Manuelle Prüfung.**" in report
    assert "NB-CRD-001" in report or "NB-RSK-001" in report
    assert report.endswith("ENDE DES GEPRÜFTEN BERICHTS")
    assert "## Empfehlung" in report
    assert "Monatliche Rate" in report
    assert "Executive Recommendation" not in report
    assert "monthly payment" not in report
    assert "Risikoklasse:" in report
    assert all(
        tool in report
        for tool in (
            "get_customer_case",
            "analyze_financial_case",
            "check_compliance",
            "search_internal_knowledge",
        )
    )
    assert "echten lokalen MCP-stdio-Sitzung" in report
    assert "Maximum" not in report
    assert "Höchstwert 40,00 %" in report
    assert "28.750,00 EUR" in report
