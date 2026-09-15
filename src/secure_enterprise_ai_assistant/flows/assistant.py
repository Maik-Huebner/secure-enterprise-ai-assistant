"""CrewAI Flow coordinating deterministic routing and specialist execution."""

from __future__ import annotations

from crewai.flow.flow import Flow, listen, router, start
from pydantic import BaseModel, Field

from secure_enterprise_ai_assistant.agents.factory import CrewOrchestrator
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.guardrails import validate_user_query
from secure_enterprise_ai_assistant.models.orchestration import RouteDecision, TraceEvent


class AssistantFlowState(BaseModel):
    """Serializable state persisted by CrewAI Flow if persistence is enabled."""

    query: str = ""
    route: RouteDecision | None = None
    answer: str = ""
    trace: list[TraceEvent] = Field(default_factory=list)


class NovaBankAssistantFlow(Flow[AssistantFlowState]):
    """Route requests to the smallest CrewAI/MCP workflow."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("tracing", False)
        kwargs.setdefault("suppress_flow_events", True)
        super().__init__(**kwargs)

    @start()
    def receive_request(self) -> str:
        self.state.query = validate_user_query(self.state.query)
        self.state.trace.append(TraceEvent(event="request_received", detail="Request received"))
        return self.state.query

    @router(receive_request)
    def select_route(self, query: str) -> str:
        self.state.route = IntentRouter().classify(query)
        self.state.trace.append(
            TraceEvent(
                event="intent_classified",
                detail=self.state.route.intent.value,
            )
        )
        return self.state.route.intent.value

    def _execute_selected_route(self) -> str:
        if self.state.route is None:
            raise RuntimeError("Flow route has not been selected.")
        orchestrator = CrewOrchestrator()
        selection = orchestrator.select_model(self.state.route)
        self.state.trace.extend(
            [
                TraceEvent(event="model_selected", detail=selection.model),
                TraceEvent(event="model_profile", detail=selection.profile.value),
                TraceEvent(event="model_reason", detail=selection.reason),
            ]
        )
        self.state.trace.append(
            TraceEvent(
                event="tools_selected",
                detail=", ".join(self.state.route.required_tools),
            )
        )
        self.state.answer = orchestrator.run(
            self.state.query,
            self.state.route,
            selection,
        )
        if orchestrator.fallback_reason is not None:
            self.state.trace.append(
                TraceEvent(event="fallback_reason", detail=orchestrator.fallback_reason)
            )
        self.state.trace.extend(
            [
                TraceEvent(event="execution_mode", detail=orchestrator.execution_mode),
                TraceEvent(event="workflow_completed", detail="Workflow completed"),
            ]
        )
        return self.state.answer

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
