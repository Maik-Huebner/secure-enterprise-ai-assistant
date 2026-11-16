"""Deterministic, auditable routing before any model or tool execution.

Two steps, neither of which calls a language model:

1. A rule extracts the case ID ("CASE-00031", "case-00031", or "Fall 31").
2. The intent of a case request is chosen semantically by comparing the request with labelled
   example requests (``resources/routing/intent_examples.json``) when a semantic embedder is
   available; otherwise keyword rules decide. Requests without a case ID are knowledge queries.
"""

from __future__ import annotations

import json
import re
from functools import cache
from typing import Literal

import numpy as np

from secure_enterprise_ai_assistant.models.orchestration import QueryIntent, RouteDecision
from secure_enterprise_ai_assistant.rag.embeddings import Embedder
from secure_enterprise_ai_assistant.resources import INTENT_EXAMPLES_PATH

CASE_PATTERN = re.compile(r"\bCASE-(\d{5})\b", re.IGNORECASE)
FALL_PATTERN = re.compile(r"\bFall\s+(?:Nr\.?\s*)?(\d{1,5})\b", re.IGNORECASE)

# Keyword stems derived from the intent examples and the routing dev split only.
FULL_ASSESSMENT_TERMS = (
    "vollständig",
    "entscheidungsvorlage",
    "gesamtbewertung",
    "komplett",
    "abschließend",
    "empfehl",
    "empfiehl",
    "genehmig",
    "full assessment",
    "fully assess",
    "decision brief",
)
COMPLIANCE_TERMS = (
    "compliance",
    "richtlinie",
    "regel",
    "verstoß",
    "verstöß",
    "verletz",
    "kyc",
    "befund",
    "vorgabe",
    "gültig",
    "policy",
    "rule",
)
FINANCIAL_TERMS = (
    "berechne",
    "rechne",
    "rate",
    "belastung",
    "schuldendienst",
    "dti",
    "zins",
    "rückzahlung",
    "monatlich",
    "kostet",
    "zahl",
    "finanz",
    "monthly payment",
    "financial",
)

TOOLS_BY_INTENT: dict[QueryIntent, list[str]] = {
    QueryIntent.KNOWLEDGE: ["search_internal_knowledge"],
    QueryIntent.CUSTOMER_CASE: ["get_customer_case"],
    QueryIntent.FINANCIAL_ANALYSIS: ["get_customer_case", "analyze_financial_case"],
    QueryIntent.COMPLIANCE_CHECK: [
        "get_customer_case",
        "check_compliance",
        "search_internal_knowledge",
    ],
    QueryIntent.FULL_ASSESSMENT: [
        "get_customer_case",
        "analyze_financial_case",
        "check_compliance",
        "search_internal_knowledge",
    ],
}

RouterMode = Literal["keyword", "semantic", "hybrid"]


def extract_case_id(query: str) -> str | None:
    """Return a normalized CASE-00000 identifier mentioned in the query."""
    match = CASE_PATTERN.search(query) or FALL_PATTERN.search(query)
    if not match:
        return None
    return f"CASE-{int(match.group(1)):05d}"


def _without_case_reference(query: str) -> str:
    return FALL_PATTERN.sub("Fall", CASE_PATTERN.sub("CASE", query))


def keyword_intent(query: str) -> QueryIntent | None:
    """Return the intent indicated by explicit keywords, or ``None`` if none matched."""
    normalized = " ".join(query.casefold().split())
    for intent, terms in (
        (QueryIntent.FULL_ASSESSMENT, FULL_ASSESSMENT_TERMS),
        (QueryIntent.COMPLIANCE_CHECK, COMPLIANCE_TERMS),
        (QueryIntent.FINANCIAL_ANALYSIS, FINANCIAL_TERMS),
    ):
        if any(term in normalized for term in terms):
            return intent
    return None


@cache
def _examples() -> dict[QueryIntent, list[str]]:
    payload = json.loads(INTENT_EXAMPLES_PATH.read_text(encoding="utf-8"))
    return {QueryIntent(name): values for name, values in payload.items() if name != "description"}


class SemanticIntentClassifier:
    """Nearest-example classifier over the labelled case-intent examples."""

    def __init__(self, embedder: Embedder, neighbours: int = 2) -> None:
        self._embedder = embedder
        self._neighbours = neighbours
        examples = _examples()
        self._labels = [intent for intent, texts in examples.items() for _ in texts]
        texts = [_without_case_reference(text) for values in examples.values() for text in values]
        self._vectors = embedder.encode_queries(texts)

    def classify(self, query: str) -> QueryIntent:
        vector = self._embedder.encode_queries([_without_case_reference(query)])[0]
        similarities = self._vectors @ vector
        scores: dict[QueryIntent, float] = {}
        for intent in set(self._labels):
            values = sorted(
                (
                    float(score)
                    for score, label in zip(similarities, self._labels, strict=True)
                    if label == intent
                ),
                reverse=True,
            )
            scores[intent] = float(np.mean(values[: self._neighbours]))
        return max(scores, key=lambda intent: scores[intent])


class IntentRouter:
    """Select the smallest safe workflow that can answer a user request."""

    def __init__(self, embedder: Embedder | None = None, mode: RouterMode = "hybrid") -> None:
        self.mode: RouterMode = mode if embedder is not None and embedder.is_semantic else "keyword"
        self._classifier = (
            SemanticIntentClassifier(embedder)
            if embedder is not None and self.mode != "keyword"
            else None
        )

    def classify(self, query: str) -> RouteDecision:
        """Classify a German or English request without calling a language model."""
        case_id = extract_case_id(query)
        method: Literal["keyword", "semantic", "rule"] = "rule"
        if case_id is None:
            intent = QueryIntent.KNOWLEDGE
        else:
            keyword = keyword_intent(query)
            if self._classifier is None or (self.mode == "hybrid" and keyword is not None):
                intent = keyword or QueryIntent.CUSTOMER_CASE
                method = "keyword"
            else:
                intent = self._classifier.classify(query)
                method = "semantic"
        return RouteDecision(
            intent=intent,
            case_id=case_id,
            required_tools=TOOLS_BY_INTENT[intent],
            routing_method=method,
        )


@cache
def _cached_router(backend: str, model: str, mode: RouterMode) -> IntentRouter:
    # Imported lazily: rag.service depends on settings and would otherwise load at import time.
    from secure_enterprise_ai_assistant.core.settings import get_settings
    from secure_enterprise_ai_assistant.rag.service import build_embedder

    del backend, model  # part of the cache key only
    return IntentRouter(build_embedder(get_settings()), mode)


def get_router() -> IntentRouter:
    """Return the process-wide router from the settings; example vectors are built once."""
    from secure_enterprise_ai_assistant.core.settings import get_settings

    settings = get_settings()
    return _cached_router(
        settings.embedding_backend, settings.embedding_model, settings.router_mode
    )
