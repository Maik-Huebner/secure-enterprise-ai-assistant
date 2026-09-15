"""Deterministic, auditable routing before any model or tool execution."""

from __future__ import annotations

import re

from secure_enterprise_ai_assistant.models.orchestration import QueryIntent, RouteDecision

CASE_PATTERN = re.compile(r"\bCASE-\d{5}\b", re.IGNORECASE)
FULL_ASSESSMENT_TERMS = (
    "vollständig",
    "entscheidungsvorlage",
    "komplette prüfung",
    "full assessment",
    "fully assess",
    "decision brief",
)
COMPLIANCE_TERMS = (
    "compliance",
    "richtlinie",
    "policy-abgleich",
    "regelverstoß",
    "regelverstoss",
)
FINANCIAL_TERMS = (
    "berechne",
    "kreditbelastung",
    "schuldendienstquote",
    "monatliche rate",
    "dti",
    "financial analysis",
    "monthly payment",
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


class IntentRouter:
    """Select the smallest safe workflow that can answer a user request."""

    def classify(self, query: str) -> RouteDecision:
        """Classify German or English demo queries without an LLM dependency."""
        normalized = " ".join(query.casefold().split())
        case_match = CASE_PATTERN.search(query)
        case_id = case_match.group(0).upper() if case_match else None
        if case_id and any(term in normalized for term in FULL_ASSESSMENT_TERMS):
            intent = QueryIntent.FULL_ASSESSMENT
        elif case_id and any(term in normalized for term in COMPLIANCE_TERMS):
            intent = QueryIntent.COMPLIANCE_CHECK
        elif case_id and any(term in normalized for term in FINANCIAL_TERMS):
            intent = QueryIntent.FINANCIAL_ANALYSIS
        elif case_id:
            intent = QueryIntent.CUSTOMER_CASE
        else:
            intent = QueryIntent.KNOWLEDGE
        return RouteDecision(
            intent=intent,
            case_id=case_id,
            required_tools=TOOLS_BY_INTENT[intent],
        )
