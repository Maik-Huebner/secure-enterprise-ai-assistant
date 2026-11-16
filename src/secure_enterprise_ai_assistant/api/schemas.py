"""Request and response schemas of the public REST API (v1)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from secure_enterprise_ai_assistant.models.orchestration import TraceEvent


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    username: str = Field(min_length=3, max_length=64, examples=["anna.becker"])
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Lebensdauer in Sekunden")


class MeResponse(StrictModel):
    username: str
    role: str
    team: str | None
    may_request_decision_brief: bool
    document_classes: list[str]


class CaseSummary(StrictModel):
    case_id: str
    customer_name: str
    requested_amount_eur: Decimal
    term_months: int


class SearchRequest(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    document_id: str | None = Field(default=None, max_length=20)


class ChatRequest(StrictModel):
    message: str = Field(min_length=3, max_length=2000)


class ChatResponse(StrictModel):
    answer: str
    intent: str
    case_id: str | None
    routing_method: str
    execution_mode: str | None
    sources: list[str]
    trace: list[TraceEvent]


class HealthResponse(StrictModel):
    status: Literal["ok"]


class ReadinessResponse(StrictModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, bool]


class Problem(StrictModel):
    """RFC 9457 problem details."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    request_id: str | None = None
