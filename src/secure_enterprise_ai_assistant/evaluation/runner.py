"""Reproducible offline evaluation for routing, tools, finance, rules, and retrieval."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secure_enterprise_ai_assistant.flows.router import TOOLS_BY_INTENT, IntentRouter
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SUITE = PROJECT_ROOT / "data" / "demo" / "evaluation_suite.json"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "evaluation" / "latest.json"


def _ratio(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


def run_evaluation(suite_path: Path = DEFAULT_SUITE) -> dict[str, Any]:
    """Run deterministic measurements; never fabricate unavailable LLM benchmarks."""
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    router = IntentRouter()
    tools = MCPToolService.build_default()

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
        tools.search_internal_knowledge(question).out_of_scope
        for question in suite["out_of_scope"]
    )
    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "dataset": "NOVABANK-SYNTHETIC-CREDIT-CASES-V1",
        "metrics": {
            "routing_accuracy": _ratio(routing_correct, len(suite["routing"])),
            "tool_selection_accuracy": _ratio(selection_correct, len(suite["routing"])),
            "financial_calculation_exact_match": _ratio(
                financial_correct, len(suite["financial"])
            ),
            "compliance_rule_exact_match": _ratio(
                compliance_correct, len(suite["compliance"])
            ),
            "retrieval_recall_at_5": _ratio(retrieval_hits, len(suite["retrieval"])),
            "source_attribution_rate": _ratio(attributed, len(suite["retrieval"])),
            "out_of_scope_accuracy": _ratio(
                out_of_scope_correct, len(suite["out_of_scope"])
            ),
        },
        "comparisons": {
            "llm_only": "not_run_requires_local_model",
            "rag": "measured_offline",
            "agentic_rag_mcp_verification": "requires_demo_runtime",
        },
    }


def main() -> None:
    """Run the suite and persist only measured values."""
    report = run_evaluation()
    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
