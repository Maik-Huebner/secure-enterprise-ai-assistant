"""Unit tests for NovaBank domain models."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from secure_enterprise_ai_assistant.models.domain import (
    ApplicationStatus,
    CreditApplication,
    CreditCase,
    CustomerDocument,
    CustomerProfile,
    DocumentStatus,
    EmploymentStatus,
    KYCStatus,
    RiskClass,
)


def build_customer() -> CustomerProfile:
    return CustomerProfile(
        customer_id="C-10284",
        full_name="Anna Becker",
        age=42,
        employment_status=EmploymentStatus.PERMANENT,
        months_employed=86,
        monthly_net_income_eur=Decimal("4850.00"),
        existing_monthly_debt_eur=Decimal("540.00"),
        risk_class=RiskClass.B,
        kyc_status=KYCStatus.VERIFIED,
    )


def build_application() -> CreditApplication:
    return CreditApplication(
        application_id="A-20317",
        customer_id="C-10284",
        requested_amount_eur=Decimal("35000.00"),
        term_months=60,
        annual_interest_rate_pct=Decimal("6.40"),
        purpose="Vehicle purchase",
        status=ApplicationStatus.SUBMITTED,
    )


def test_valid_credit_case() -> None:
    case = CreditCase(
        case_id="CASE-00001",
        customer=build_customer(),
        application=build_application(),
        documents=[
            CustomerDocument(
                document_type="Identity document",
                status=DocumentStatus.PRESENT,
            ),
            CustomerDocument(
                document_type="Income statement",
                status=DocumentStatus.PRESENT,
            ),
        ],
    )

    assert case.customer.customer_id == "C-10284"
    assert case.application.requested_amount_eur == Decimal("35000.00")
    assert len(case.documents) == 2


def test_customer_id_must_follow_schema() -> None:
    with pytest.raises(ValidationError):
        CustomerProfile(
            customer_id="INVALID",
            full_name="Anna Becker",
            age=42,
            employment_status=EmploymentStatus.PERMANENT,
            months_employed=86,
            monthly_net_income_eur=Decimal("4850.00"),
            existing_monthly_debt_eur=Decimal("540.00"),
            risk_class=RiskClass.B,
            kyc_status=KYCStatus.VERIFIED,
        )


def test_case_rejects_mismatched_customer() -> None:
    application = build_application().model_copy(update={"customer_id": "C-99999"})

    with pytest.raises(
        ValueError,
        match="customer_id des Kreditantrags",
    ):
        CreditCase(
            case_id="CASE-00001",
            customer=build_customer(),
            application=application,
        )


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        # The unknown field is the point of this test; mypy rejects it statically as well.
        CustomerProfile(  # type: ignore[call-arg]
            customer_id="C-10284",
            full_name="Anna Becker",
            age=42,
            employment_status=EmploymentStatus.PERMANENT,
            months_employed=86,
            monthly_net_income_eur=Decimal("4850.00"),
            existing_monthly_debt_eur=Decimal("540.00"),
            risk_class=RiskClass.B,
            kyc_status=KYCStatus.VERIFIED,
            secret_field="should-not-be-accepted",
        )
