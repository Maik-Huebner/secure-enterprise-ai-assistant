"""Routing and tool-selection accuracy tests for documented demo scenarios."""

import pytest

from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?",
            QueryIntent.KNOWLEDGE,
        ),
        ("Zeige CASE-00001.", QueryIntent.CUSTOMER_CASE),
        ("Berechne die Kreditbelastung für CASE-00001.", QueryIntent.FINANCIAL_ANALYSIS),
        ("Welche Compliance-Probleme hat CASE-00017?", QueryIntent.COMPLIANCE_CHECK),
        (
            "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage.",
            QueryIntent.FULL_ASSESSMENT,
        ),
    ],
)
def test_demo_query_routing(query: str, expected: QueryIntent) -> None:
    decision = IntentRouter().classify(query)

    assert decision.intent == expected
    assert decision.required_tools


def test_router_selects_only_required_tools() -> None:
    router = IntentRouter()

    assert router.classify("Zeige CASE-00001").required_tools == ["get_customer_case"]
    assert router.classify("What is the KYC policy?").required_tools == [
        "search_internal_knowledge"
    ]
