"""Smoke tests for the Gradio application and safe controller errors."""

import json
import subprocess
import sys

from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.models.orchestration import TraceEvent
from secure_enterprise_ai_assistant.ui.app import (
    GRADIO_UI_LOCALIZATION_JS,
    AssistantController,
)


def _probe_ui_in_subprocess() -> dict[str, object]:
    """Build Gradio outside Pytest's process to isolate its Python 3.13 cleanup."""
    code = """
import json
from secure_enterprise_ai_assistant.ui.app import build_app
app = build_app()
visible = []
for component in app.config["components"]:
    properties = component.get("props", {})
    visible.append({key: properties[key] for key in (
        "label", "value", "placeholder", "headers", "title"
    ) if key in properties})
print("UI_PROBE=" + json.dumps({"title": app.title, "visible": visible}, ensure_ascii=False))
app.close()
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    marker = next(
        line.removeprefix("UI_PROBE=")
        for line in completed.stdout.splitlines()
        if line.startswith("UI_PROBE=")
    )
    probe = json.loads(marker)
    assert isinstance(probe, dict)
    return probe


def test_gradio_blocks_builds_without_launching() -> None:
    assert _probe_ui_in_subprocess()["title"] == "Sicherer Enterprise-KI-Assistent"


def test_rendered_ui_configuration_has_no_english_navigation_labels() -> None:
    rendered = json.dumps(_probe_ui_in_subprocess()["visible"], ensure_ascii=False)

    forbidden_labels = (
        "Execution Trace",
        "Sources",
        "Knowledge",
        "Documents",
        "System / Diagnostics",
        "Selected model",
        "Execution mode",
        "Fallback reason",
        "Request",
    )
    assert all(label not in rendered for label in forbidden_labels)
    assert "Ausführungsprotokoll" in rendered
    assert "Wissensbasis & Dokumente" in rendered
    assert "System / Diagnose" in rendered
    assert "Prüfung starten" in rendered


def test_gradio_builtin_controls_are_localized_for_the_browser() -> None:
    english_builtin_labels = (
        "Copy conversation",
        "Copy message",
        "user's message",
        "Loading response",
        "Loading content",
        "processing",
        "Empty value",
        "Table actions",
        "Copy table data",
        "Fullscreen",
        "More tabs",
        "Open cell menu",
        "File upload",
        "Line number",
        "Collapse",
        "Expand",
        "Object",
        "Copy",
    )
    german_builtin_labels = (
        "Unterhaltung kopieren",
        "Nachricht kopieren",
        "Anfrage des Benutzers",
        "Antwort wird geladen",
        "Inhalt wird geladen",
        "Verarbeitung",
        "Kein Wert vorhanden",
        "Tabellenaktionen",
        "Tabellendaten kopieren",
        "Vollbild",
        "Weitere Tabs",
        "Zellenmenü öffnen",
        "Datei hochladen",
        "Zeilennummer",
        "Einklappen",
        "Ausklappen",
        "Objekt",
        "Kopieren",
    )

    assert all(label in GRADIO_UI_LOCALIZATION_JS for label in english_builtin_labels)
    assert all(label in GRADIO_UI_LOCALIZATION_JS for label in german_builtin_labels)


def test_controller_does_not_expose_internal_exception() -> None:
    def fail(_query):
        raise RuntimeError("SECRET_INTERNAL_DETAIL")

    controller = AssistantController(flow_runner=fail)
    history, sources, trace, tools, status = controller.submit("Hello", [])

    rendered = str((history, sources, trace, tools, status))
    assert "SECRET_INTERNAL_DETAIL" not in rendered
    assert "Ollama" in history[-1]["content"]
    assert "Der lokale Workflow konnte nicht abgeschlossen werden" in rendered


def test_controller_localizes_visible_error_for_german_request() -> None:
    def fail(_query):
        raise RuntimeError("SECRET_INTERNAL_DETAIL")

    controller = AssistantController(flow_runner=fail)
    history, sources, _trace, _tools, status = controller.submit(
        "Berechne die finanzielle Belastung für CASE-00031.", []
    )

    rendered = str((history, sources, status))
    assert "SECRET_INTERNAL_DETAIL" not in rendered
    assert "Der lokale Workflow konnte nicht abgeschlossen werden" in rendered
    assert "Keine Quellen" in sources
    assert "Workflow nicht verfügbar" in status


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
    assert tools["Ausgewähltes Modell"] == "qwen3.5:9b"
    assert tools["Modellprofil"] == "Schnell und lokal"
    assert tools["Ausführungsmodus"] == "CrewAI"
    assert trace[0][1] == "Modell ausgewählt"
    assert trace[1][1] == "Modellprofil"
    assert trace[2][1] == "Ausführungsmodus"
    assert "qwen3.5:9b" in status


def test_controller_exposes_full_assessment_safe_mode_transparently() -> None:
    route = IntentRouter().classify(
        "Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."
    )
    technical_trace = [
        TraceEvent(event="configured_complex_model", detail="mistral-small3.2:24b"),
        TraceEvent(event="model_profile", detail="complex_agentic"),
        TraceEvent(event="full_assessment_mode", detail="verified_mcp"),
        TraceEvent(
            event="fallback_reason",
            detail=(
                "Demo-Safe-Modus – verifizierter MCP-Pfad für reproduzierbare lokale Ausführung"
            ),
        ),
        TraceEvent(event="execution_mode", detail="deterministic_mcp_fallback"),
    ]
    controller = AssistantController(
        flow_runner=lambda _query: ("Verifizierter Bericht", route, technical_trace)
    )

    _history, _sources, trace, tools, status = controller.submit("demo", [])

    assert "Ausgewähltes Modell" not in tools
    assert tools["Konfiguriertes komplexes Modell"] == "mistral-small3.2:24b"
    assert tools["Modellprofil"] == "Komplex und agentisch"
    assert tools["Modus für vollständige Prüfung"] == "Verifizierter MCP-Pfad"
    assert tools["Ausführungsmodus"] == "Deterministischer MCP-Fallback"
    assert tools["Fallback-Grund"].startswith("Demo-Safe-Modus")
    assert any(row[1] == "Konfiguriertes komplexes Modell" for row in trace)
    assert "wurde nicht ausgeführt" in status


def test_case_view_localizes_visible_field_names_and_values() -> None:
    case_view = AssistantController().case_view("CASE-00001")

    assert "Fall" in case_view
    assert "case" not in case_view
    assert case_view["Fall"]["Fall-ID"] == "CASE-00001"
    assert case_view["Fall"]["Kunde"]["Beschäftigungsstatus"] == ("unbefristet beschäftigt")
    assert case_view["Fall"]["Kreditantrag"]["Verwendungszweck"] == (
        "Energieeffiziente Wohnungsmodernisierung"
    )
    assert case_view["Fall"]["Dokumente"][0]["Dokumenttyp"] == "Identitätsnachweis"


def test_diagnostics_uses_german_presentation_labels() -> None:
    diagnostics = AssistantController().diagnostics()

    assert "Umgebung" in diagnostics
    assert "MCP-Status" in diagnostics
    assert "MCP-Werkzeuge" in diagnostics
    assert "Synthetische Fälle" in diagnostics
    assert "Dokumente in der Wissensbasis" in diagnostics
    assert "Externe Cloud erforderlich" in diagnostics
    assert "environment" not in diagnostics
    assert "mcp_tools" not in diagnostics
