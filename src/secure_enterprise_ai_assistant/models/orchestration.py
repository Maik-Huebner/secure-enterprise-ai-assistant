"""Schemas for routing, safe execution traces, and assistant responses."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from secure_enterprise_ai_assistant.models.domain import DomainModel


class QueryIntent(StrEnum):
    """Supported workflow routes."""

    KNOWLEDGE = "knowledge"
    CUSTOMER_CASE = "customer_case"
    FINANCIAL_ANALYSIS = "financial_analysis"
    COMPLIANCE_CHECK = "compliance_check"
    FULL_ASSESSMENT = "full_assessment"


class RouteDecision(DomainModel):
    """Auditable route and exact MCP allowlist selected for one query."""

    intent: QueryIntent
    case_id: str | None = Field(default=None, pattern=r"^CASE-\d{5}$")
    required_tools: list[str]
    routing_method: Literal["rule", "keyword", "semantic"] = "keyword"


class TraceEvent(DomainModel):
    """Technical execution event that contains no private model reasoning."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event: str
    detail: str


class AssistantResponse(DomainModel):
    """Final UI-facing response envelope."""

    answer: str
    route: RouteDecision
    trace: list[TraceEvent]
    source_references: list[str] = Field(default_factory=list)
