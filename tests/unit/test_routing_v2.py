"""Tests for case-ID extraction, keyword fallback and the semantic intent classifier."""

from __future__ import annotations

import json
from collections.abc import Sequence

import numpy as np
import pytest

from secure_enterprise_ai_assistant.flows.router import (
    IntentRouter,
    extract_case_id,
    keyword_intent,
)
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent
from secure_enterprise_ai_assistant.rag.embeddings import HashingEmbedder
from secure_enterprise_ai_assistant.resources import INTENT_EXAMPLES_PATH, ROUTING_SUITE_PATH


class FakeSemanticEmbedder:
    is_semantic = True
    name = "fake-semantic"

    def __init__(self) -> None:
        self._inner = HashingEmbedder()

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._inner.encode_documents(texts)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._inner.encode_queries(texts)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Zeige CASE-00031.", "CASE-00031"),
        ("zeige case-00031", "CASE-00031"),
        ("Berechne die Rate für Fall 31.", "CASE-00031"),
        ("Prüfe Fall Nr. 7 vollständig.", "CASE-00007"),
        ("Welche Risikoklassen sind zulässig?", None),
    ],
)
def test_case_id_extraction(query: str, expected: str | None) -> None:
    assert extract_case_id(query) == expected


def test_requests_without_case_id_are_knowledge_queries_by_rule() -> None:
    decision = IntentRouter(FakeSemanticEmbedder()).classify("Wer darf Ausnahmen genehmigen?")

    assert decision.intent == QueryIntent.KNOWLEDGE
    assert decision.routing_method == "rule"


def test_hashing_embedder_falls_back_to_keywords() -> None:
    router = IntentRouter(HashingEmbedder(), "semantic")

    assert router.mode == "keyword"
    assert router.classify("Berechne die Rate für CASE-00001.").routing_method == "keyword"


def test_semantic_mode_uses_the_example_classifier() -> None:
    router = IntentRouter(FakeSemanticEmbedder(), "semantic")
    decision = router.classify("Erstelle eine Entscheidungsvorlage für CASE-00002.")

    assert decision.routing_method == "semantic"
    assert decision.intent == QueryIntent.FULL_ASSESSMENT


def test_hybrid_mode_prefers_explicit_keywords() -> None:
    decision = IntentRouter(FakeSemanticEmbedder(), "hybrid").classify(
        "Welche Compliance-Probleme hat CASE-00017?"
    )

    assert decision.intent == QueryIntent.COMPLIANCE_CHECK
    assert decision.routing_method == "keyword"


def test_keyword_rules_cover_the_audit_paraphrases() -> None:
    assert keyword_intent("Wie hoch ist die Rate für CASE-00001?") == QueryIntent.FINANCIAL_ANALYSIS
    assert keyword_intent("Gibt es KYC-Probleme bei CASE-00008?") == QueryIntent.COMPLIANCE_CHECK
    assert keyword_intent("Soll CASE-00031 genehmigt werden?") == QueryIntent.FULL_ASSESSMENT
    assert keyword_intent("Zeige CASE-00001.") is None


def test_intent_examples_do_not_leak_into_the_routing_suite() -> None:
    examples = json.loads(INTENT_EXAMPLES_PATH.read_text(encoding="utf-8"))
    suite = json.loads(ROUTING_SUITE_PATH.read_text(encoding="utf-8"))
    example_texts = {
        text for key, values in examples.items() if key != "description" for text in values
    }
    suite_texts = {query for split in ("dev", "test") for query, _ in suite[split]}

    assert not example_texts & suite_texts
    assert len(suite["dev"]) + len(suite["test"]) >= 40
