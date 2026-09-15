"""Smoke tests for the Gradio application and safe controller errors."""

from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.models.orchestration import TraceEvent
from secure_enterprise_ai_assistant.ui.app import AssistantController, build_app


def test_gradio_blocks_builds_without_launching() -> None:
    app = build_app()

    assert app.title == "Secure Enterprise AI Assistant"


def test_controller_does_not_expose_internal_exception() -> None:
    def fail(_query):
        raise RuntimeError("SECRET_INTERNAL_DETAIL")

    controller = AssistantController(flow_runner=fail)
    history, sources, trace, tools, status = controller.submit("Hello", [])

    rendered = str((history, sources, trace, tools, status))
    assert "SECRET_INTERNAL_DETAIL" not in rendered
    assert "Ollama" in history[-1]["content"]


def test_controller_exposes_model_and_execution_metadata() -> None:
    route = IntentRouter().classify("Berechne die Kreditbelastung für CASE-00031.")
    technical_trace = [
        TraceEvent(event="model_selected", detail="qwen3.5:9b"),
        TraceEvent(event="model_profile", detail="fast_local"),
        TraceEvent(event="execution_mode", detail="crewai"),
    ]
    controller = AssistantController(
        flow_runner=lambda _query: ("MCP result", route, technical_trace)
    )

    _history, _sources, trace, tools, status = controller.submit("demo", [])

    assert len(trace) == 3
    assert tools["model"] == "qwen3.5:9b"
    assert tools["model_profile"] == "fast_local"
    assert tools["execution_mode"] == "crewai"
    assert "qwen3.5:9b" in status
