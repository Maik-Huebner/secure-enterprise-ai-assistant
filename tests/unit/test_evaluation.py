"""Smoke test for reproducible measured evaluation."""

from secure_enterprise_ai_assistant.evaluation import run_evaluation


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
    }
    assert all(0 <= value <= 1 for value in report["metrics"].values())
    assert report["comparisons"]["llm_only"] == "not_run_requires_local_model"
