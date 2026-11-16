"""Unit tests for deterministic Decimal-based loan calculations."""

from decimal import Decimal

from secure_enterprise_ai_assistant.development.synthetic_data import build_dataset
from secure_enterprise_ai_assistant.services.financial_analysis import FinancialAnalysisService


def test_annuity_and_dti_metrics_are_deterministic() -> None:
    cases, _ = build_dataset()
    metrics = FinancialAnalysisService().analyze(cases[0])

    assert metrics.monthly_payment_eur == Decimal("419.46")
    assert metrics.total_repayment_eur == Decimal("20134.08")
    assert metrics.total_interest_eur == Decimal("1884.08")
    assert metrics.debt_to_income_before_pct == Decimal("4.00")
    assert metrics.debt_to_income_after_pct == Decimal("10.71")
    assert metrics.debt_to_income_change_pct_points == Decimal("6.71")
    assert metrics.monthly_obligations_after_eur == (
        cases[0].customer.existing_monthly_debt_eur + metrics.monthly_payment_eur
    )


def test_high_debt_case_has_higher_post_loan_dti() -> None:
    cases, _ = build_dataset()
    high_debt_case = next(
        case for case in cases if case.customer.existing_monthly_debt_eur == Decimal("1450.00")
    )
    metrics = FinancialAnalysisService().analyze(high_debt_case)

    assert metrics.debt_to_income_after_pct > metrics.debt_to_income_before_pct
    assert metrics.debt_to_income_after_pct > Decimal("50.00")
