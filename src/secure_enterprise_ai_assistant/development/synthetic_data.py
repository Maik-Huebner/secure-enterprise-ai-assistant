"""Generate the reproducible, fully synthetic NovaBank credit-case dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from secure_enterprise_ai_assistant.core.company import PROJECT_DISCLAIMER
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

DATASET_SEED = 20260914


@dataclass(frozen=True)
class Scenario:
    """Input parameters and evaluation label for one synthetic case archetype."""

    name: str
    income: Decimal
    existing_debt: Decimal
    amount: Decimal
    term: int
    interest_rate: Decimal
    employment: EmploymentStatus
    months_employed: int
    risk_class: RiskClass
    kyc_status: KYCStatus
    income_document: DocumentStatus
    identity_document: DocumentStatus
    ground_truth: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "strong_affordability",
        Decimal("6200.00"),
        Decimal("250.00"),
        Decimal("18000.00"),
        48,
        Decimal("4.90"),
        EmploymentStatus.PERMANENT,
        84,
        RiskClass.A,
        KYCStatus.VERIFIED,
        DocumentStatus.PRESENT,
        DocumentStatus.PRESENT,
        "approve",
    ),
    Scenario(
        "standard_affordability",
        Decimal("4100.00"),
        Decimal("520.00"),
        Decimal("26000.00"),
        60,
        Decimal("6.20"),
        EmploymentStatus.PERMANENT,
        46,
        RiskClass.B,
        KYCStatus.VERIFIED,
        DocumentStatus.PRESENT,
        DocumentStatus.PRESENT,
        "approve",
    ),
    Scenario(
        "borderline_dti",
        Decimal("3300.00"),
        Decimal("980.00"),
        Decimal("28500.00"),
        60,
        Decimal("7.10"),
        EmploymentStatus.PERMANENT,
        31,
        RiskClass.C,
        KYCStatus.VERIFIED,
        DocumentStatus.PRESENT,
        DocumentStatus.PRESENT,
        "manual_review",
    ),
    Scenario(
        "missing_income_document",
        Decimal("3900.00"),
        Decimal("430.00"),
        Decimal("22000.00"),
        48,
        Decimal("6.40"),
        EmploymentStatus.PERMANENT,
        38,
        RiskClass.B,
        KYCStatus.VERIFIED,
        DocumentStatus.MISSING,
        DocumentStatus.PRESENT,
        "manual_review",
    ),
    Scenario(
        "kyc_pending",
        Decimal("4700.00"),
        Decimal("360.00"),
        Decimal("24000.00"),
        60,
        Decimal("5.80"),
        EmploymentStatus.PERMANENT,
        55,
        RiskClass.B,
        KYCStatus.PENDING,
        DocumentStatus.PRESENT,
        DocumentStatus.PRESENT,
        "manual_review",
    ),
    Scenario(
        "temporary_employment",
        Decimal("3600.00"),
        Decimal("410.00"),
        Decimal("19500.00"),
        48,
        Decimal("7.40"),
        EmploymentStatus.TEMPORARY,
        8,
        RiskClass.C,
        KYCStatus.VERIFIED,
        DocumentStatus.PRESENT,
        DocumentStatus.PRESENT,
        "manual_review",
    ),
    Scenario(
        "high_debt_load",
        Decimal("3200.00"),
        Decimal("1450.00"),
        Decimal("30000.00"),
        48,
        Decimal("9.20"),
        EmploymentStatus.PERMANENT,
        27,
        RiskClass.D,
        KYCStatus.VERIFIED,
        DocumentStatus.PRESENT,
        DocumentStatus.PRESENT,
        "decline",
    ),
    Scenario(
        "kyc_rejected",
        Decimal("5000.00"),
        Decimal("300.00"),
        Decimal("20000.00"),
        48,
        Decimal("6.00"),
        EmploymentStatus.PERMANENT,
        62,
        RiskClass.E,
        KYCStatus.REJECTED,
        DocumentStatus.PRESENT,
        DocumentStatus.INVALID,
        "decline",
    ),
)

FIRST_NAMES = ("Mara", "Jonas", "Nele", "Tobias", "Aylin", "Daniel", "Sofia", "Leon")
LAST_NAMES = ("Winter", "Falk", "Berger", "Kern", "Adler", "Lind", "West", "Brandt")


def _scenario_for(case_number: int) -> Scenario:
    """Return a stable scenario, preserving the documented demo cases."""
    demo_overrides = {
        1: "strong_affordability",
        17: "missing_income_document",
        31: "borderline_dti",
    }
    scenario_name = demo_overrides.get(case_number)
    if scenario_name is not None:
        return next(item for item in SCENARIOS if item.name == scenario_name)
    return SCENARIOS[(case_number - 1) % len(SCENARIOS)]


def build_dataset(case_count: int = 48) -> tuple[list[CreditCase], dict[str, object]]:
    """Build deterministic cases and a separate evaluation-only ground-truth file."""
    if case_count < 40:
        raise ValueError("The NovaBank portfolio dataset must contain at least 40 cases.")

    cases: list[CreditCase] = []
    labels: dict[str, str] = {}
    scenarios: dict[str, str] = {}

    for number in range(1, case_count + 1):
        scenario = _scenario_for(number)
        customer_id = f"C-{10000 + number:05d}"
        case_id = f"CASE-{number:05d}"
        amount_variation = Decimal((number % 5) * 250)
        income_variation = Decimal((number % 4) * 50)
        customer = CustomerProfile(
            customer_id=customer_id,
            full_name=(
                f"{FIRST_NAMES[(number - 1) % len(FIRST_NAMES)]} "
                f"{LAST_NAMES[((number - 1) // len(FIRST_NAMES)) % len(LAST_NAMES)]}"
            ),
            age=24 + (number * 7) % 39,
            employment_status=scenario.employment,
            months_employed=scenario.months_employed + number % 6,
            monthly_net_income_eur=scenario.income + income_variation,
            existing_monthly_debt_eur=scenario.existing_debt,
            risk_class=scenario.risk_class,
            kyc_status=scenario.kyc_status,
        )
        application = CreditApplication(
            application_id=f"A-{20000 + number:05d}",
            customer_id=customer_id,
            requested_amount_eur=scenario.amount + amount_variation,
            term_months=scenario.term,
            annual_interest_rate_pct=scenario.interest_rate,
            purpose=("Energy-efficient home improvement" if number % 2 else "Vehicle purchase"),
            status=ApplicationStatus.UNDER_REVIEW,
        )
        documents = [
            CustomerDocument(
                document_type="identity_document",
                status=scenario.identity_document,
            ),
            CustomerDocument(
                document_type="income_statement",
                status=scenario.income_document,
            ),
            CustomerDocument(
                document_type="bank_statements_90_days",
                status=DocumentStatus.PRESENT,
            ),
            CustomerDocument(
                document_type="credit_application_form",
                status=DocumentStatus.PRESENT,
            ),
        ]
        cases.append(
            CreditCase(
                case_id=case_id,
                customer=customer,
                application=application,
                documents=documents,
            )
        )
        labels[case_id] = scenario.ground_truth
        scenarios[case_id] = scenario.name

    ground_truth: dict[str, object] = {
        "dataset_seed": DATASET_SEED,
        "synthetic_data_disclaimer": PROJECT_DISCLAIMER,
        "labels_are_evaluation_only": True,
        "decision_labels": labels,
        "scenario_labels": scenarios,
    }
    return cases, ground_truth


def write_dataset(
    cases_path: Path,
    labels_path: Path,
    case_count: int = 48,
) -> None:
    """Write stable UTF-8 JSON artifacts with evaluation labels kept separate."""
    cases, ground_truth = build_dataset(case_count)
    cases_payload = {
        "dataset_id": "NOVABANK-SYNTHETIC-CREDIT-CASES-V1",
        "dataset_seed": DATASET_SEED,
        "synthetic_data_disclaimer": PROJECT_DISCLAIMER,
        "case_count": len(cases),
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    for path, payload in ((cases_path, cases_payload), (labels_path, ground_truth)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
