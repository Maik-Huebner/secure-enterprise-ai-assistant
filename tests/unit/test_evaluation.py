"""Regression tests for reproducible measured evaluation evidence."""

import json

import pytest

from secure_enterprise_ai_assistant.evaluation import run_evaluation, validate_evidence
from secure_enterprise_ai_assistant.evaluation.evidence import EvidenceValidationError


def test_offline_evaluation_metrics_are_measured() -> None:
    report = run_evaluation()

    expected = {
        "financial_calculation_exact_match",
        "compliance_rule_exact_match",
        "routing_keyword_dev_accuracy",
        "routing_keyword_test_accuracy",
        "guardrail_dev_attack_recall",
        "guardrail_dev_false_positive_rate",
        "guardrail_holdout_attack_recall",
        "guardrail_holdout_false_positive_rate",
    } | {
        f"retrieval_hashing_{split}_{name}"
        for split in ("dev", "test")
        for name in ("recall_at_5", "mrr", "ndcg_at_5", "no_answer_accuracy")
    }
    assert set(report["metrics"]) == expected
    assert all(0 <= value <= 1 for value in report["metrics"].values())
    assert (
        report["counts"]["retrieval_dev_questions"] + report["counts"]["retrieval_test_questions"]
        >= 30
    )
    assert report["counts"]["routing_dev_queries"] + report["counts"]["routing_test_queries"] >= 40
    assert all(len(value) == 64 for value in report["inputs"].values())


def test_tautological_metrics_were_removed() -> None:
    report = run_evaluation()

    assert "tool_selection_accuracy" not in report["metrics"]
    assert "source_attribution_rate" not in report["metrics"]


def test_metric_notes_refer_to_reported_metrics() -> None:
    report = run_evaluation()

    assert report["metric_notes"]
    assert set(report["metric_notes"]) <= set(report["metrics"])


def test_evidence_validator_rejects_manipulated_metric(tmp_path) -> None:
    report = run_evaluation()
    report["metrics"]["retrieval_recall_at_5"] = 0.0
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="metrics"):
        validate_evidence(path)
