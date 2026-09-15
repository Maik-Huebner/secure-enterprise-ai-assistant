"""Structured output contracts exposed through MCP."""

from pydantic import Field

from secure_enterprise_ai_assistant.models.domain import (
    ComplianceFinding,
    CreditCase,
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


class ComplianceCheckResult(DomainModel):
    """MCP response containing all configured compliance findings."""

    case_id: str = Field(pattern=r"^CASE-\d{5}$")
    findings: list[ComplianceFinding]
