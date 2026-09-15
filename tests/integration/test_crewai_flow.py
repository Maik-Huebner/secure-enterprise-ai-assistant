"""Integration test for CrewAI Flow branch dispatch without a live model."""

from secure_enterprise_ai_assistant.agents.factory import CrewOrchestrator
from secure_enterprise_ai_assistant.flows import NovaBankAssistantFlow
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent


def test_flow_dispatches_router_result_to_workflow(monkeypatch) -> None:
    monkeypatch.setattr(
        CrewOrchestrator,
        "run",
        lambda _self, _query, _route, _selection=None: "stubbed specialist output",
    )
    flow = NovaBankAssistantFlow()

    result = flow.kickoff(inputs={"query": "Zeige CASE-00001."})

    assert result == "stubbed specialist output"
    assert flow.state.route is not None
    assert flow.state.route.intent == QueryIntent.CUSTOMER_CASE
    assert [event.event for event in flow.state.trace] == [
        "request_received",
        "intent_classified",
        "model_selected",
        "model_profile",
        "model_reason",
        "tools_selected",
        "execution_mode",
        "workflow_completed",
    ]
    trace = {event.event: event.detail for event in flow.state.trace}
    assert trace["model_selected"] == "qwen3.5:9b"
    assert trace["model_profile"] == "fast_local"
    assert trace["execution_mode"] == "crewai"


def test_full_assessment_trace_exposes_mistral_and_fallback(monkeypatch) -> None:
    def fallback(
        orchestrator: CrewOrchestrator,
        _query: str,
        _route: object,
        _selection: object = None,
    ) -> str:
        orchestrator.execution_mode = "deterministic_mcp_fallback"
        orchestrator.fallback_reason = "Native guardrail rejected incomplete output"
        return "verified fallback output"

    monkeypatch.setattr(CrewOrchestrator, "run", fallback)
    flow = NovaBankAssistantFlow()

    result = flow.kickoff(
        inputs={
            "query": (
                "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage "
                "einschließlich finanzieller Kennzahlen, Policy-Abgleich, "
                "Compliance-Risiken und Quellen."
            )
        }
    )

    trace = {event.event: event.detail for event in flow.state.trace}
    assert result == "verified fallback output"
    assert trace["model_selected"] == "mistral-small3.2:24b"
    assert trace["model_profile"] == "complex_agentic"
    assert trace["fallback_reason"] == "Native guardrail rejected incomplete output"
    assert trace["execution_mode"] == "deterministic_mcp_fallback"
