"""CrewAI Flow coordinating deterministic routing and specialist execution."""

from __future__ import annotations

import warnings
from typing import Any

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"Cannot set an attribute on 'crewai\.rag' for child module 'embeddings'",
        category=ImportWarning,
    )
    from crewai.flow.flow import Flow, listen, router, start
from pydantic import BaseModel, Field

from secure_enterprise_ai_assistant.agents.factory import CrewOrchestrator
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.guardrails import validate_user_query
from secure_enterprise_ai_assistant.models.orchestration import (
    QueryIntent,
    RouteDecision,
    TraceEvent,
)


class AssistantFlowState(BaseModel):
    """Serializable state persisted by CrewAI Flow if persistence is enabled."""

    query: str = ""
    route: RouteDecision | None = None
    answer: str = ""
    trace: list[TraceEvent] = Field(default_factory=list)


class NovaBankAssistantFlow(Flow[AssistantFlowState]):
    """Route requests to the smallest CrewAI/MCP workflow."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("tracing", False)
        kwargs.setdefault("suppress_flow_events", True)
        super().__init__(**kwargs)

    @property
    def typed_state(self) -> AssistantFlowState:
        """Return the Flow state narrowed to its declared model at runtime."""
        state = self.state
        if not isinstance(state, AssistantFlowState):
            raise TypeError("Flow state has an unexpected type.")
        return state

    @start()
    def receive_request(self) -> str:
        state = self.typed_state
        state.query = validate_user_query(state.query)
        state.trace.append(TraceEvent(event="request_received", detail="Request received"))
        return state.query

    @router(receive_request)
    def select_route(self, query: str) -> str:
        state = self.typed_state
        route = IntentRouter().classify(query)
        state.route = route
        state.trace.append(TraceEvent(event="intent_classified", detail=route.intent.value))
        return route.intent.value

    def _execute_selected_route(self) -> str:
        state = self.typed_state
        if state.route is None:
            raise RuntimeError("Flow route has not been selected.")
        orchestrator = CrewOrchestrator()
        selection = orchestrator.select_model(state.route)
        demo_safe_mode = (
            state.route.intent == QueryIntent.FULL_ASSESSMENT
            and orchestrator.factory.settings.full_assessment_mode == "verified_mcp"
        )
        if demo_safe_mode:
            state.trace.extend(
                [
                    TraceEvent(event="configured_complex_model", detail=selection.model),
                    TraceEvent(event="model_profile", detail=selection.profile.value),
                    TraceEvent(event="model_reason", detail=selection.reason),
                    TraceEvent(event="full_assessment_mode", detail="verified_mcp"),
                ]
            )
        else:
            state.trace.extend(
                [
                    TraceEvent(event="model_selected", detail=selection.model),
                    TraceEvent(event="model_profile", detail=selection.profile.value),
                    TraceEvent(event="model_reason", detail=selection.reason),
                ]
            )
        state.trace.append(
            TraceEvent(
                event="tools_selected",
                detail=", ".join(state.route.required_tools),
            )
        )
        answer = orchestrator.run(state.query, state.route, selection)
        state.answer = answer
        if orchestrator.fallback_reason is not None:
            state.trace.append(
                TraceEvent(event="fallback_reason", detail=orchestrator.fallback_reason)
            )
        state.trace.extend(
            [
                TraceEvent(event="execution_mode", detail=orchestrator.execution_mode),
                TraceEvent(event="workflow_completed", detail="Workflow completed"),
            ]
        )
        return answer

    @listen("knowledge")
    def execute_knowledge_route(self) -> str:
        return self._execute_selected_route()

    @listen("customer_case")
    def execute_customer_route(self) -> str:
        return self._execute_selected_route()

    @listen("financial_analysis")
    def execute_financial_route(self) -> str:
        return self._execute_selected_route()

    @listen("compliance_check")
    def execute_compliance_route(self) -> str:
        return self._execute_selected_route()

    @listen("full_assessment")
    def execute_full_assessment_route(self) -> str:
        return self._execute_selected_route()
