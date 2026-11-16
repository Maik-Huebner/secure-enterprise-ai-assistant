"""Deterministic scoring helpers of the answer-quality evaluation."""

import json

from secure_enterprise_ai_assistant.evaluation.answer_quality import (
    citation_check,
    declined,
    fact_hits,
    ratio,
)
from secure_enterprise_ai_assistant.graph.evidence_text import NO_ANSWER
from secure_enterprise_ai_assistant.resources import RESOURCE_ROOT


def test_fact_hits_accept_alternative_spellings() -> None:
    answer = "Nötig sind Ausweis, Kontoauszug der letzten 90 Tage (NB-DOC-001)."

    assert fact_hits(answer, [["Ausweis"], ["Kontoauszüge", "Kontoauszug"], ["Einkommen"]]) == [
        True,
        True,
        False,
    ]


def test_the_wrong_paket_1_answer_would_be_scored_incorrect() -> None:
    hallucinated = (
        "Benötigt werden Ausweis, Einkommensnachweis, Schuldenverzeichnis und eine "
        "Selbstständigkeitserklärung (NB-DOC-001)."
    )
    facts = [["Ausweis"], ["Einkommensnachweis"], ["Kontoauszüge"], ["90 Tage"], ["Kreditantrag"]]

    assert not all(fact_hits(hallucinated, facts))


def test_citation_check() -> None:
    result = citation_check("Siehe NB-DOC-001 und NB-XYZ-999.", {"NB-DOC-001"}, ["NB-DOC-001"])

    assert result["only_grounded_cited"] is False
    assert result["expected_cited"] is True


def test_declined_recognizes_the_no_answer_text() -> None:
    assert declined(NO_ANSWER)
    assert not declined("Die Rate beträgt 570,64 EUR.")


def test_ratio_ignores_not_applicable_values() -> None:
    assert ratio([True, False, None]) == 0.5
    assert ratio([None]) is None


def test_answer_suite_is_well_formed() -> None:
    suite = json.loads((RESOURCE_ROOT / "evaluation" / "answer_suite.json").read_text())["items"]

    assert len(suite) >= 15
    assert {item["kind"] for item in suite} >= {"knowledge", "no_answer", "financial", "compliance"}
    assert all(item["facts"] or item["kind"] == "no_answer" for item in suite)
