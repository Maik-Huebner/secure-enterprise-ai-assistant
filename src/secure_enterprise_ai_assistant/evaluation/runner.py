"""Reproducible offline evaluation for routing, tools, retrieval, and guardrails."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from secure_enterprise_ai_assistant.flows.router import TOOLS_BY_INTENT, IntentRouter
from secure_enterprise_ai_assistant.guardrails import UnsafeInputError, validate_user_query
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent
from secure_enterprise_ai_assistant.resources import (
    CASES_PATH,
    EVALUATION_SUITE_PATH,
    KNOWLEDGE_ROOT,
    RULES_PATH,
)

DEFAULT_SUITE = EVALUATION_SUITE_PATH


def _ratio(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.glob("*")):
        if path.is_file():
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def run_evaluation(
    suite_path: Path = DEFAULT_SUITE,
    tools: MCPToolService | None = None,
) -> dict[str, Any]:
    """Run deterministic measurements without requiring a model or network access."""
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    router = IntentRouter()
    tools = tools or MCPToolService.build_default()

    routing_correct = 0
    selection_correct = 0
    for query, expected_value in suite["routing"]:
        expected = QueryIntent(expected_value)
        decision = router.classify(query)
        routing_correct += decision.intent == expected
        selection_correct += decision.required_tools == TOOLS_BY_INTENT[expected]

    financial_correct = 0
    for case_id, expected in suite["financial"].items():
        metrics = tools.analyze_financial_case(case_id).metrics
        actual = [
            str(metrics.monthly_payment_eur),
            str(metrics.debt_to_income_before_pct),
            str(metrics.debt_to_income_after_pct),
            str(metrics.total_interest_eur),
            str(metrics.total_repayment_eur),
        ]
        financial_correct += actual == expected

    compliance_correct = 0
    for case_id, expected in suite["compliance"].items():
        actual = [
            item.rule_id for item in tools.check_compliance(case_id).findings if not item.passed
        ]
        compliance_correct += actual == expected

    retrieval_hits = 0
    attributed = 0
    for question, expected_document in suite["retrieval"]:
        response = tools.search_internal_knowledge(question, top_k=5)
        documents = {item.chunk.document_id for item in response.results}
        retrieval_hits += expected_document in documents
        attributed += bool(response.results) and all(
            item.chunk.document_id and item.chunk.title and item.chunk.section
            for item in response.results
        )

    out_of_scope_correct = sum(
        tools.search_internal_knowledge(question).out_of_scope for question in suite["out_of_scope"]
    )
    guardrail_correct = 0
    for item in suite["guardrails"]:
        blocked = False
        try:
            validate_user_query(item["query"])
        except UnsafeInputError:
            blocked = True
        guardrail_correct += blocked is item["blocked"]

    counts = {
        "routing_queries": len(suite["routing"]),
        "financial_cases": len(suite["financial"]),
        "compliance_cases": len(suite["compliance"]),
        "retrieval_queries": len(suite["retrieval"]),
        "out_of_scope_queries": len(suite["out_of_scope"]),
        "guardrail_queries": len(suite["guardrails"]),
    }
    return {
        "schema_version": 1,
        "suite": "secure_enterprise_ai_assistant/resources/evaluation/evaluation_suite.json",
        "dataset": "NOVABANK-SYNTHETIC-CREDIT-CASES-V1",
        "inputs": {
            "suite_sha256": _sha256(suite_path),
            "cases_sha256": _sha256(CASES_PATH),
            "rules_sha256": _sha256(RULES_PATH),
            "knowledge_corpus_sha256": _corpus_sha256(KNOWLEDGE_ROOT),
        },
        "counts": counts,
        "metrics": {
            "routing_accuracy": _ratio(routing_correct, counts["routing_queries"]),
            "tool_selection_accuracy": _ratio(selection_correct, counts["routing_queries"]),
            "financial_calculation_exact_match": _ratio(
                financial_correct, counts["financial_cases"]
            ),
            "compliance_rule_exact_match": _ratio(compliance_correct, counts["compliance_cases"]),
            "retrieval_recall_at_5": _ratio(retrieval_hits, counts["retrieval_queries"]),
            "source_attribution_rate": _ratio(attributed, counts["retrieval_queries"]),
            "out_of_scope_accuracy": _ratio(out_of_scope_correct, counts["out_of_scope_queries"]),
            "input_guardrail_accuracy": _ratio(guardrail_correct, counts["guardrail_queries"]),
        },
        "comparisons": {
            "llm_only": "not_run_requires_local_model",
            "rag": "measured_offline",
            "agentic_rag_mcp_verification": "requires_demo_runtime",
        },
        "limitations": (
            "Small synthetic regression suite; it does not measure real lending quality, "
            "legal compliance, free-form model accuracy, or production security."
        ),
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    """Persist a deterministic evidence report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Run the offline suite and optionally persist the deterministic report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(args.suite)
    if args.output is not None:
        write_report(report, args.output)
    print(json.dumps(report["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
