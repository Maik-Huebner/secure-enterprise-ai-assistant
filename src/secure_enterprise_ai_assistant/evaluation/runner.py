"""Reproducible offline evaluation (no model, no network): the CI baseline.

Retrieval and routing here use the deterministic hashing embedder and keyword rules, because CI
has no Ollama. Measurements with real embedding models are produced locally by
``scripts/benchmark_retrieval.py`` and ``scripts/benchmark_routing.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from secure_enterprise_ai_assistant.evaluation.retrieval_metrics import metrics, observe
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.guardrails import detect_attack_categories
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.rag.embeddings import HashingEmbedder
from secure_enterprise_ai_assistant.rag.service import KnowledgeService
from secure_enterprise_ai_assistant.resources import (
    CASES_PATH,
    EVALUATION_SUITE_PATH,
    GUARDRAIL_SUITE_PATH,
    KNOWLEDGE_ROOT,
    RETRIEVAL_SUITE_PATH,
    ROUTING_SUITE_PATH,
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


def offline_tools() -> MCPToolService:
    """Tool service with the deterministic hashing baseline, independent of local settings."""
    return MCPToolService.build(KnowledgeService.from_directory(embedder=HashingEmbedder()))


def run_evaluation(
    suite_path: Path = DEFAULT_SUITE,
    tools: MCPToolService | None = None,
) -> dict[str, Any]:
    """Run deterministic measurements without requiring a model or network access."""
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    tools = tools or offline_tools()
    measured: dict[str, float] = {}
    counts: dict[str, int] = {}

    routing = json.loads(ROUTING_SUITE_PATH.read_text(encoding="utf-8"))
    router = IntentRouter()
    for split in ("dev", "test"):
        items = routing[split]
        correct = sum(router.classify(query).intent.value == expected for query, expected in items)
        measured[f"routing_keyword_{split}_accuracy"] = _ratio(correct, len(items))
        counts[f"routing_{split}_queries"] = len(items)

    financial_correct = 0
    for case_id, expected in suite["financial"].items():
        financial = tools.analyze_financial_case(case_id).metrics
        actual = [
            str(financial.monthly_payment_eur),
            str(financial.debt_to_income_before_pct),
            str(financial.debt_to_income_after_pct),
            str(financial.total_interest_eur),
            str(financial.total_repayment_eur),
        ]
        financial_correct += actual == expected
    measured["financial_calculation_exact_match"] = _ratio(
        financial_correct, len(suite["financial"])
    )
    counts["financial_cases"] = len(suite["financial"])

    compliance_correct = 0
    for case_id, expected in suite["compliance"].items():
        failed = [
            item.rule_id for item in tools.check_compliance(case_id).findings if not item.passed
        ]
        compliance_correct += failed == expected
    measured["compliance_rule_exact_match"] = _ratio(compliance_correct, len(suite["compliance"]))
    counts["compliance_cases"] = len(suite["compliance"])

    retrieval = json.loads(RETRIEVAL_SUITE_PATH.read_text(encoding="utf-8"))

    def search(question: str) -> KnowledgeSearchResponse:
        return tools.search_internal_knowledge(question, top_k=5)

    for split in ("dev", "test"):
        retrieval_result = metrics(observe(search, retrieval[split]))
        for name in ("recall_at_5", "mrr", "ndcg_at_5", "no_answer_accuracy"):
            measured[f"retrieval_hashing_{split}_{name}"] = retrieval_result[name]
        counts[f"retrieval_{split}_questions"] = len(retrieval[split])

    guardrail_suite = json.loads(GUARDRAIL_SUITE_PATH.read_text(encoding="utf-8"))
    for split in ("dev", "holdout"):
        attacks = guardrail_suite[split]["attacks"]
        benign = guardrail_suite[split]["benign"]
        blocked = sum(bool(detect_attack_categories(query)) for query in attacks)
        false_positives = sum(bool(detect_attack_categories(query)) for query in benign)
        measured[f"guardrail_{split}_attack_recall"] = _ratio(blocked, len(attacks))
        measured[f"guardrail_{split}_false_positive_rate"] = _ratio(false_positives, len(benign))
        counts[f"guardrail_{split}_attacks"] = len(attacks)
        counts[f"guardrail_{split}_benign"] = len(benign)

    return {
        "schema_version": 2,
        "suite": "secure_enterprise_ai_assistant/resources/evaluation/",
        "dataset": "NOVABANK-SYNTHETIC-CREDIT-CASES-V1",
        "inputs": {
            "suite_sha256": _sha256(suite_path),
            "routing_suite_sha256": _sha256(ROUTING_SUITE_PATH),
            "retrieval_suite_sha256": _sha256(RETRIEVAL_SUITE_PATH),
            "guardrail_suite_sha256": _sha256(GUARDRAIL_SUITE_PATH),
            "cases_sha256": _sha256(CASES_PATH),
            "rules_sha256": _sha256(RULES_PATH),
            "knowledge_corpus_sha256": _corpus_sha256(KNOWLEDGE_ROOT),
        },
        "counts": counts,
        "metrics": measured,
        "metric_notes": {
            "routing_keyword_test_accuracy": (
                "Keyword baseline only; the semantic/hybrid router needs Ollama and is reported "
                "in reports/evaluation/routing_comparison.json."
            ),
            "retrieval_hashing_test_recall_at_5": (
                "Hashing baseline only; real embedding models are compared in "
                "reports/evaluation/retrieval_comparison.json."
            ),
            "guardrail_dev_attack_recall": (
                "The dev split was used to design the patterns and is optimistic by construction."
            ),
            "guardrail_holdout_attack_recall": (
                "The holdout split was written after the patterns and measured without tuning. "
                "Both splits were written by the pattern author, so this is no independent "
                "benchmark."
            ),
        },
        "comparisons": {
            "llm_only": "not_run_requires_local_model",
            "rag": "measured_offline_hashing_baseline",
            "agentic_rag_mcp_verification": "requires_demo_runtime",
        },
        "limitations": (
            "Small synthetic suites written by the project author; they do not measure real "
            "lending quality, legal compliance, free-form model accuracy, or production security."
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
