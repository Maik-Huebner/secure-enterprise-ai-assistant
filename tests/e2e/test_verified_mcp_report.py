"""Evidence over a real MCP stdio session and the deterministic decision brief."""

from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.mcp.client import McpEvidenceClient, render_decision_brief
from tests.conftest import REVIEWER, token_for


def test_verified_report_uses_all_structured_evidence() -> None:
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )

    evidence = McpEvidenceClient(token_for(REVIEWER)).collect(route, "nicht verwendet")
    report = render_decision_brief("CASE-00031", evidence)

    assert set(evidence) == {"case", "financial", "compliance", "knowledge"}
    assert evidence["compliance"]["decision"]["recommendation"] == "manual_review"
    assert "Sofia Kern" in report
    assert "570,64 EUR" in report
    assert "28,41 %" in report and "44,95 %" in report
    assert "5.488,40 EUR" in report
    assert "RULE-005" in report and "nicht bestanden" in report
    assert "**Empfehlung: Manuelle Prüfung.**" in report
    assert "NB-CRD-001" in report or "NB-RSK-001" in report
    assert report.endswith("ENDE DES GEPRÜFTEN BERICHTS")
    assert "Höchstwert 40,00 %" in report
    assert "28.750,00 EUR" in report
    assert "monthly payment" not in report
