"""Deterministic consumer-credit calculations using decimal arithmetic."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext

from secure_enterprise_ai_assistant.models.domain import CreditCase, FinancialMetrics

CENT = Decimal("0.01")
PERCENT = Decimal("0.01")
MONTHS_PER_YEAR = Decimal(12)
PERCENT_DENOMINATOR = Decimal(100)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _percentage(value: Decimal) -> Decimal:
    return value.quantize(PERCENT, rounding=ROUND_HALF_UP)


class FinancialAnalysisService:
    """Calculate auditable affordability metrics without LLM involvement."""

    def analyze(self, case: CreditCase) -> FinancialMetrics:
        """Calculate an annuity payment and DTI metrics for a validated case."""
        application = case.application
        customer = case.customer
        principal = application.requested_amount_eur
        periods = application.term_months

        with localcontext() as context:
            context.prec = 28
            monthly_rate = (
                application.annual_interest_rate_pct / PERCENT_DENOMINATOR / MONTHS_PER_YEAR
            )
            if monthly_rate == 0:
                unrounded_payment = principal / Decimal(periods)
            else:
                discount_factor = Decimal(1) - (Decimal(1) + monthly_rate) ** (-periods)
                unrounded_payment = principal * monthly_rate / discount_factor

            monthly_payment = _money(unrounded_payment)
            total_repayment = _money(monthly_payment * periods)
            total_interest = _money(total_repayment - principal)
            dti_before = _percentage(
                customer.existing_monthly_debt_eur
                / customer.monthly_net_income_eur
                * PERCENT_DENOMINATOR
            )
            dti_after = _percentage(
                (customer.existing_monthly_debt_eur + monthly_payment)
                / customer.monthly_net_income_eur
                * PERCENT_DENOMINATOR
            )

        return FinancialMetrics(
            monthly_payment_eur=monthly_payment,
            debt_to_income_before_pct=dti_before,
            debt_to_income_after_pct=dti_after,
            total_interest_eur=total_interest,
            total_repayment_eur=total_repayment,
        )
