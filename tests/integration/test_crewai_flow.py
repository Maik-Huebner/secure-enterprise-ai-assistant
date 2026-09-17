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


def test_full_assessment_trace_exposes_demo_safe_mode_without_claiming_model_run(
    monkeypatch,
) -> None:
    def fallback(
        orchestrator: CrewOrchestrator,
        _query: str,
        _route: object,
        _selection: object = None,
    ) -> str:
        orchestrator.execution_mode = "deterministic_mcp_fallback"
        orchestrator.fallback_reason = (
            "Demo-Safe-Modus – verifizierter MCP-Pfad für reproduzierbare lokale Ausführung"
        )
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
    assert "model_selected" not in trace
    assert trace["configured_complex_model"] == "mistral-small3.2:24b"
    assert trace["model_profile"] == "complex_agentic"
    assert trace["full_assessment_mode"] == "verified_mcp"
    assert trace["fallback_reason"].startswith("Demo-Safe-Modus")
    assert trace["execution_mode"] == "deterministic_mcp_fallback"
    assert trace["tools_selected"] == (
        "get_customer_case, analyze_financial_case, check_compliance, "
        "search_internal_knowledge"
    )
