"""Regression tests for reproducible measured evaluation evidence."""

import json

import pytest

from secure_enterprise_ai_assistant.evaluation import run_evaluation, validate_evidence
from secure_enterprise_ai_assistant.evaluation.evidence import EvidenceValidationError


def test_offline_evaluation_metrics_are_measured() -> None:
    report = run_evaluation()

    assert set(report["metrics"]) == {
        "routing_accuracy",
        "tool_selection_accuracy",
        "financial_calculation_exact_match",
        "compliance_rule_exact_match",
        "retrieval_recall_at_5",
        "source_attribution_rate",
        "out_of_scope_accuracy",
        "input_guardrail_accuracy",
    }
    assert all(0 <= value <= 1 for value in report["metrics"].values())
    assert report["comparisons"]["llm_only"] == "not_run_requires_local_model"
    assert all(len(value) == 64 for value in report["inputs"].values())


def test_metric_notes_refer_to_reported_metrics() -> None:
    report = run_evaluation()

    assert report["metric_notes"]
    assert set(report["metric_notes"]) <= set(report["metrics"])
    assert "by construction" in report["metric_notes"]["tool_selection_accuracy"]


def test_evidence_validator_rejects_manipulated_metric(tmp_path) -> None:
    report = run_evaluation()
    report["metrics"]["retrieval_recall_at_5"] = 0.0
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="metrics"):
        validate_evidence(path)
