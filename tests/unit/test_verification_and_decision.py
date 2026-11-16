"""Answer verification rules and rule-based decision support."""

from __future__ import annotations

from decimal import Decimal

import pytest

from secure_enterprise_ai_assistant.graph.verification import (
    interpretations,
    unsupported_numbers,
    verify_answer,
)
from secure_enterprise_ai_assistant.models.domain import DecisionRecommendation
from secure_enterprise_ai_assistant.services.compliance import ComplianceService
from secure_enterprise_ai_assistant.services.decision import DecisionService
from tests.api_support import offline_tools
from tests.conftest import REVIEWER

KNOWLEDGE = {
    "knowledge": {
        "out_of_scope": False,
        "results": [
            {
                "chunk": {
                    "document_id": "NB-DOC-001",
                    "section": "3.1 Pflichtnachweise",
                    "title": "Richtlinie",
                    "version": "1.7",
                    "content": "Kontoauszüge der letzten 90 Tage und ein Einkommensnachweis.",
                }
            }
        ],
    }
}


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("570,64", {Decimal("570.64"), Decimal("57064")}),
        ("18.250,00", {Decimal("18250"), Decimal("18.25")}),
        ("44.95", {Decimal("44.95"), Decimal("4495")}),
        ("90", {Decimal("90")}),
    ],
)
def test_number_readings(token: str, expected: set[Decimal]) -> None:
    assert expected <= interpretations(token)


def test_numbers_in_german_and_english_notation_are_both_accepted() -> None:
    allowed = interpretations("570,64") | interpretations("44,95")

    assert unsupported_numbers("Rate 570.64 EUR, DTI 44,95 %", allowed) == []
    assert unsupported_numbers("Rate 571,00 EUR", allowed) == ["571,00"]
    assert unsupported_numbers("Schritt 3 von 4", set()) == []  # small counters are ignored


def test_grounded_answer_passes() -> None:
    answer = "Nötig sind Kontoauszüge der letzten 90 Tage (NB-DOC-001, Abschnitt 3.1)."

    assert verify_answer(answer, KNOWLEDGE) == []


@pytest.mark.parametrize(
    ("answer", "fragment"),
    [
        ("Nötig sind Kontoauszüge der letzten 120 Tage (NB-DOC-001).", "Zahlen"),
        ("Nötig sind Kontoauszüge (NB-KYC-001, Abschnitt 2).", "nicht gefunden"),
        ("Nötig sind Kontoauszüge der letzten 90 Tage.", "Dokument-ID"),
        ("Monthly Payment: siehe NB-DOC-001.", "englischer"),
    ],
)
def test_ungrounded_answers_are_reported(answer: str, fragment: str) -> None:
    issues = verify_answer(answer, KNOWLEDGE)

    assert any(fragment in issue for issue in issues), issues


def test_hard_decline_flags_come_from_the_ruleset() -> None:
    rules = ComplianceService.from_json().rules

    assert {rule.rule_id for rule in rules if rule.hard_decline} == {
        "RULE-001",
        "RULE-006",
        "RULE-007",
    }


@pytest.mark.parametrize(
    ("case_id", "expected"),
    [
        ("CASE-00001", DecisionRecommendation.APPROVE),
        ("CASE-00031", DecisionRecommendation.MANUAL_REVIEW),
        ("CASE-00017", DecisionRecommendation.MANUAL_REVIEW),
        ("CASE-00007", DecisionRecommendation.DECLINE),
        ("CASE-00008", DecisionRecommendation.DECLINE),
    ],
)
def test_compliance_tool_returns_rule_based_recommendation(
    case_id: str, expected: DecisionRecommendation
) -> None:
    result = offline_tools().check_compliance(case_id, principal=REVIEWER)

    assert result.decision.recommendation == expected
    assert set(result.decision.hard_decline_rules) <= set(result.decision.failed_rules)


def test_decision_service_without_findings_recommends_approval() -> None:
    summary = DecisionService(ComplianceService.from_json().rules).summarize([])

    assert summary.recommendation == DecisionRecommendation.APPROVE


def test_cross_references_inside_the_evidence_may_be_cited() -> None:
    evidence = {
        "knowledge": {
            "out_of_scope": False,
            "results": [
                {
                    "chunk": {
                        "document_id": "NB-KYC-001",
                        "section": "4.3 Abgelehnte Verifizierung",
                        "title": "KYC",
                        "version": "3.1",
                        "content": "Nicht genehmigen; Eskalation nach NB-ESC-001.",
                    }
                }
            ],
        }
    }
    answer = "Nicht genehmigen und nach NB-ESC-001 eskalieren (NB-KYC-001, Abschnitt 4.3)."

    assert verify_answer(answer, evidence) == []


def test_placeholder_document_ids_are_rejected() -> None:
    issues = verify_answer("Siehe NB-DOC-XXX und NB-DOC-001, Abschnitt 3.1.", KNOWLEDGE)

    assert any("Platzhalter" in issue for issue in issues)


def test_compliance_evidence_contains_the_failed_rules_own_source() -> None:
    from secure_enterprise_ai_assistant.flows.router import IntentRouter
    from tests.api_support import InProcessCollector
    from tests.conftest import token_for

    route = IntentRouter().classify("Welche Compliance-Probleme hat CASE-00017?")
    evidence = InProcessCollector(token_for(REVIEWER)).collect(route, "unused")

    failed = [item for item in evidence["compliance"]["findings"] if not item["passed"]]
    assert failed[0]["source_document_id"] == "NB-DOC-001"
    documents = [item["chunk"]["document_id"] for item in evidence["knowledge"]["results"]]
    assert documents[0] == "NB-DOC-001"
