"""Core domain models for the fictional NovaBank environment."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    """Base class for strict domain models."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class EmploymentStatus(StrEnum):
    """Employment status used in fictional retail lending cases."""

    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    SELF_EMPLOYED = "self_employed"
    RETIRED = "retired"
    STUDENT = "student"
    UNEMPLOYED = "unemployed"


class KYCStatus(StrEnum):
    """Know-your-customer verification status."""

    VERIFIED = "verified"
    PENDING = "pending"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"


class RiskClass(StrEnum):
    """Synthetic internal credit-risk classification."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class ApplicationStatus(StrEnum):
    """Lifecycle state of a fictional credit application."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class DocumentStatus(StrEnum):
    """Availability state of a required customer document."""

    PRESENT = "present"
    MISSING = "missing"
    EXPIRED = "expired"
    INVALID = "invalid"


class ComplianceSeverity(StrEnum):
    """Severity of a compliance-rule violation."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DecisionRecommendation(StrEnum):
    """Decision-support output produced by the system."""

    APPROVE = "approve"
    MANUAL_REVIEW = "manual_review"
    DECLINE = "decline"


class CustomerProfile(DomainModel):
    """Synthetic retail-banking customer profile."""

    customer_id: str = Field(pattern=r"^C-\d{5}$")
    full_name: str = Field(min_length=3, max_length=120)
    age: int = Field(ge=18, le=100)
    employment_status: EmploymentStatus
    months_employed: int = Field(ge=0, le=720)
    monthly_net_income_eur: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    existing_monthly_debt_eur: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    risk_class: RiskClass
    kyc_status: KYCStatus


class CreditApplication(DomainModel):
    """Synthetic consumer-credit application."""

    application_id: str = Field(pattern=r"^A-\d{5}$")
    customer_id: str = Field(pattern=r"^C-\d{5}$")
    requested_amount_eur: Decimal = Field(
        gt=0,
        le=Decimal("100000.00"),
        max_digits=10,
        decimal_places=2,
    )
    term_months: int = Field(ge=6, le=120)
    annual_interest_rate_pct: Decimal = Field(
        gt=0,
        le=Decimal("30.00"),
        max_digits=5,
        decimal_places=2,
    )
    purpose: str = Field(min_length=3, max_length=160)
    status: ApplicationStatus = ApplicationStatus.SUBMITTED


class CustomerDocument(DomainModel):
    """Document state attached to a fictional customer case."""

    document_type: str = Field(min_length=2, max_length=100)
    status: DocumentStatus


class CreditCase(DomainModel):
    """Complete fictional customer case used by MCP tools and agents."""

    case_id: str = Field(pattern=r"^CASE-\d{5}$")
    customer: CustomerProfile
    application: CreditApplication
    documents: list[CustomerDocument] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        """Ensure application and customer belong to the same case."""
        if self.customer.customer_id != self.application.customer_id:
            raise ValueError(
                "Die customer_id des Kreditantrags muss zur customer_id des Kundenprofils passen."
            )


class ComplianceRule(DomainModel):
    """Machine-readable compliance or policy rule."""

    rule_id: str = Field(pattern=r"^RULE-\d{3}$")
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=1000)
    category: str = Field(min_length=2, max_length=100)
    severity: ComplianceSeverity
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    source_document: str = Field(min_length=3, max_length=200)
    source_section: str = Field(min_length=1, max_length=200)
    # A failed hard-decline rule cannot be remedied by additional evidence (NB-GDE-001 §4).
    hard_decline: bool = False


class ComplianceFinding(DomainModel):
    """Result of evaluating one compliance rule."""

    rule_id: str = Field(pattern=r"^RULE-\d{3}$")
    passed: bool
    severity: ComplianceSeverity
    message: str = Field(min_length=3, max_length=1000)
    # Where the rule comes from, so that the matching policy section can be retrieved exactly.
    source_document_id: str | None = Field(default=None, pattern=r"^NB-[A-Z]{3}-\d{3}$")
    source_section: str | None = None


class FinancialMetrics(DomainModel):
    """Deterministic financial metrics produced by the analysis tool."""

    monthly_payment_eur: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    debt_to_income_before_pct: Decimal = Field(
        ge=0,
        max_digits=7,
        decimal_places=2,
    )
    debt_to_income_after_pct: Decimal = Field(
        ge=0,
        max_digits=7,
        decimal_places=2,
    )
    total_interest_eur: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    total_repayment_eur: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    # Derived values the language model would otherwise compute itself (and must not).
    monthly_obligations_after_eur: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    debt_to_income_change_pct_points: Decimal = Field(max_digits=7, decimal_places=2)


class CaseDecision(DomainModel):
    """Structured decision-support result."""

    case_id: str = Field(pattern=r"^CASE-\d{5}$")
    recommendation: DecisionRecommendation
    rationale: list[str] = Field(min_length=1)
    financial_metrics: FinancialMetrics
    compliance_findings: list[ComplianceFinding]
    source_references: list[str] = Field(default_factory=list)
