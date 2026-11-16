"""Structured output contracts exposed through MCP."""

from pydantic import Field

from secure_enterprise_ai_assistant.models.domain import (
    ComplianceFinding,
    CreditCase,
    DecisionRecommendation,
    DomainModel,
    FinancialMetrics,
)


class CustomerCaseResult(DomainModel):
    """MCP response containing one synthetic credit case."""

    case: CreditCase


class FinancialAnalysisResult(DomainModel):
    """MCP response containing deterministic metrics for one case."""

    case_id: str = Field(pattern=r"^CASE-\d{5}$")
    metrics: FinancialMetrics


class DecisionSummary(DomainModel):
    """Rule-derived decision support; the final decision stays with a human reviewer."""

    recommendation: DecisionRecommendation
    rationale: str = Field(min_length=3)
    failed_rules: list[str]
    hard_decline_rules: list[str]


class ComplianceCheckResult(DomainModel):
    """MCP response containing all configured compliance findings and the derived summary."""

    case_id: str = Field(pattern=r"^CASE-\d{5}$")
    findings: list[ComplianceFinding]
    decision: DecisionSummary
