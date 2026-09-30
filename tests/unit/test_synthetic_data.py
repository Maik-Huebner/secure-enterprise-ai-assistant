"""Tests for deterministic synthetic NovaBank dataset generation."""

from secure_enterprise_ai_assistant.development.synthetic_data import build_dataset, write_dataset
from secure_enterprise_ai_assistant.resources import CASES_PATH


def test_dataset_contains_required_scenarios_and_decision_groups() -> None:
    cases, ground_truth = build_dataset()

    assert len(cases) == 48
    assert len({case.case_id for case in cases}) == 48
    assert len({case.customer.customer_id for case in cases}) == 48
    scenario_labels = ground_truth["scenario_labels"]
    decision_labels = ground_truth["decision_labels"]
    assert set(scenario_labels.values()) == {
        "strong_affordability",
        "standard_affordability",
        "borderline_dti",
        "missing_income_document",
        "kyc_pending",
        "temporary_employment",
        "high_debt_load",
        "kyc_rejected",
    }
    assert set(decision_labels.values()) == {"approve", "manual_review", "decline"}


def test_documented_demo_cases_remain_stable() -> None:
    _, ground_truth = build_dataset()

    scenarios = ground_truth["scenario_labels"]
    assert scenarios["CASE-00001"] == "strong_affordability"
    assert scenarios["CASE-00017"] == "missing_income_document"
    assert scenarios["CASE-00031"] == "borderline_dti"


def test_dataset_generation_is_reproducible() -> None:
    first_cases, first_labels = build_dataset()
    second_cases, second_labels = build_dataset()

    assert first_cases == second_cases
    assert first_labels == second_labels


def test_committed_runtime_cases_match_generator(tmp_path) -> None:
    cases_path = tmp_path / "cases.json"
    labels_path = tmp_path / "labels.json"
    write_dataset(cases_path, labels_path)

    assert cases_path.read_bytes() == CASES_PATH.read_bytes()
