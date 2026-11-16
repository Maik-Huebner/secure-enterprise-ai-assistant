"""Professional Gradio Blocks interface for the local NovaBank assistant."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any

import gradio as gr
import httpx

from secure_enterprise_ai_assistant.core.company import COMPANY_NAME, PROJECT_DISCLAIMER
from secure_enterprise_ai_assistant.core.labels import CODE_LABELS
from secure_enterprise_ai_assistant.core.logs import configure_logging, get_logger, request_context
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.guardrails import UnsafeInputError
from secure_enterprise_ai_assistant.mcp import create_mcp_server
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService

SOURCE_PATTERN = re.compile(r"\bNB-[A-Z]+-\d{3}\b")
logger = get_logger(__name__)

UI_TITLE = "Sicherer Enterprise-KI-Assistent"
UI_DISCLAIMER = PROJECT_DISCLAIMER

TRACE_EVENT_LABELS = {
    "request_received": "Anfrage empfangen",
    "intent_classified": "Anfragetyp erkannt",
    "routing_method": "Erkennungsmethode",
    "model_selected": "Modell ausgewählt",
    "configured_complex_model": "Konfiguriertes komplexes Modell",
    "model_profile": "Modellprofil",
    "model_reason": "Routing-Grund",
    "full_assessment_mode": "Modus für vollständige Prüfung",
    "tools_selected": "MCP-Werkzeuge ausgewählt",
    "fallback_reason": "Fallback-Grund",
    "execution_mode": "Ausführungsmodus",
    "workflow_completed": "Ablauf abgeschlossen",
}

# Technical codes specific to routing and runtime; domain codes come from core.labels.
UI_VALUE_LABELS = {
    **CODE_LABELS,
    "knowledge": "Wissensabfrage",
    "customer_case": "Fallabfrage",
    "financial_analysis": "Finanzanalyse",
    "compliance_check": "Compliance-Prüfung",
    "full_assessment": "Vollständige Prüfung",
    "fast_local": "Schnell und lokal",
    "complex_agentic": "Komplex und agentisch",
    "crewai": "CrewAI",
    "deterministic_mcp_fallback": "Deterministischer MCP-Rückfallweg",
    "verified_mcp": "Verifizierter MCP-Pfad",
    "agentic": "Experimenteller agentischer Modus",
    "not recorded": "nicht erfasst",
    "rule": "Regel",
    "keyword": "Schlüsselwörter",
    "semantic": "Bedeutung (Embedding)",
    "development": "Entwicklung",
    "production": "Produktion",
    "test": "Test",
}

CASE_FIELD_LABELS = {
    "case": "Fall",
    "case_id": "Fall-ID",
    "customer": "Kunde",
    "customer_id": "Kunden-ID",
    "full_name": "Vollständiger Name",
    "age": "Alter",
    "employment_status": "Beschäftigungsstatus",
    "months_employed": "Beschäftigungsdauer in Monaten",
    "monthly_net_income_eur": "Monatliches Nettoeinkommen in EUR",
    "existing_monthly_debt_eur": "Bestehende monatliche Schuldenlast in EUR",
    "risk_class": "Risikoklasse",
    "kyc_status": "KYC-Status",
    "application": "Kreditantrag",
    "application_id": "Antrags-ID",
    "requested_amount_eur": "Beantragter Betrag in EUR",
    "term_months": "Laufzeit in Monaten",
    "annual_interest_rate_pct": "Jährlicher Zinssatz in Prozent",
    "purpose": "Verwendungszweck",
    "status": "Status",
    "documents": "Dokumente",
    "document_type": "Dokumenttyp",
}

CSS = """
:root { --nova-navy: #10233f; --nova-blue: #1b5eaa; --nova-mist: #eef3f8; }
.gradio-container { max-width: 1480px !important; background: #f6f8fb; }
.hero { background: linear-gradient(120deg, #10233f, #1b5eaa); color: white;
        padding: 22px 28px; border-radius: 14px; margin-bottom: 12px; }
.hero h1 { margin: 0 0 6px 0; font-size: 28px; color: #fff !important; }
.hero p { margin: 0; opacity: .9; color: #fff !important; }
.status-card { border-left: 4px solid #1b5eaa; }
footer { display: none !important; }
"""

GRADIO_UI_LOCALIZATION_JS = """
(() => {
  document.documentElement.lang = "de";
  const translations = new Map([
    ["Copy conversation", "Unterhaltung kopieren"],
    ["Copy message", "Nachricht kopieren"],
    ["chatbot conversation", "Unterhaltung mit dem Assistenten"],
    ["bot's message", "Antwort des Assistenten"],
    ["user's message", "Anfrage des Benutzers"],
    ["Loading response", "Antwort wird geladen"],
    ["Loading content", "Inhalt wird geladen"],
    ["Loading...", "Wird geladen …"],
    ["processing", "Verarbeitung"],
    ["Empty value", "Kein Wert vorhanden"],
    ["Table actions", "Tabellenaktionen"],
    ["Copy table data", "Tabellendaten kopieren"],
    ["Fullscreen", "Vollbild"],
    ["More tabs", "Weitere Tabs"],
    ["Open cell menu", "Zellenmenü öffnen"],
    ["File upload", "Datei hochladen"],
    ["Gradio footer navigation", "Gradio-Fußzeilennavigation"],
    ["Download JSON", "JSON herunterladen"],
    ["Copy JSON", "JSON kopieren"],
    ["View as JSON", "Als JSON anzeigen"],
    ["Line number", "Zeilennummer"],
    ["Collapse", "Einklappen"],
    ["Expand", "Ausklappen"],
    ["Object", "Objekt"],
    ["Copy", "Kopieren"],
    ["Close", "Schließen"],
  ]);
  const translate = (input) => {
    let output = input;
    for (const [source, target] of translations) {
      output = output.replaceAll(source, target);
    }
    return output;
  };
  const localize = (root) => {
    if (root !== document && !(root instanceof Element)) return;
    const elements = root instanceof Element
      ? [root, ...root.querySelectorAll("*")]
      : [...document.querySelectorAll("*")];
    for (const element of elements) {
      for (const attribute of ["aria-label", "title"]) {
        let value = element.getAttribute(attribute);
        if (!value) continue;
        value = translate(value);
        if (value !== element.getAttribute(attribute)) {
          element.setAttribute(attribute, value);
        }
      }
      const localizableText = element.matches(
        "button, [role='status'], [class*='progress-text'], [class*='sr-only']"
      );
      if (localizableText) {
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let textNode;
        while ((textNode = walker.nextNode())) {
          const localizedText = translate(textNode.nodeValue || "");
          if (localizedText !== textNode.nodeValue) textNode.nodeValue = localizedText;
        }
      }
    }
  };
  localize(document);
  new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "attributes") localize(record.target);
      if (record.type === "characterData") localize(record.target.parentElement);
      for (const node of record.addedNodes) localize(node);
    }
  }).observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["aria-label", "title"],
  });
})();
"""


def _ui_value(value: Any) -> Any:
    """Translate known presentation values without changing backend data."""
    if isinstance(value, dict):
        return {CASE_FIELD_LABELS.get(key, key): _ui_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_ui_value(item) for item in value]
    if isinstance(value, str):
        return UI_VALUE_LABELS.get(value, value)
    return value


def _trace_detail(event: str, detail: str) -> str:
    """Return a safe German display value for one technical trace detail."""
    if event == "fallback_reason":
        if detail.startswith("Demo-Safe-Modus"):
            return detail
        return (
            "Die native CrewAI-Ausgabe hat die Qualitätsprüfung nicht bestanden; "
            "der deterministische MCP-Fallback wurde verwendet."
        )
    return str(_ui_value(detail))


class AssistantController:
    """UI adapter that exposes safe outputs and never leaks internal exceptions."""

    def __init__(
        self,
        tools: MCPToolService | None = None,
        flow_runner: Callable[[str], tuple[str, Any, list[Any]]] | None = None,
    ) -> None:
        self.tools = tools or MCPToolService.build_default()
        self.flow_runner = flow_runner or self._run_flow

    @staticmethod
    def _run_flow(query: str) -> tuple[str, Any, list[Any]]:
        from secure_enterprise_ai_assistant.flows import NovaBankAssistantFlow

        flow = NovaBankAssistantFlow()
        answer = str(flow.kickoff(inputs={"query": query}))
        return answer, flow.state.route, flow.state.trace

    def submit(
        self, message: str, history: list[dict[str, str]] | None
    ) -> tuple[list[dict[str, str]], str, list[list[str]], dict[str, Any], str]:
        """Execute a Flow and return chat, sources, trace, tools, and status."""
        with request_context():
            return self._submit(message, history)

    def _submit(
        self, message: str, history: list[dict[str, str]] | None
    ) -> tuple[list[dict[str, str]], str, list[list[str]], dict[str, Any], str]:
        history = list(history or [])
        query = message.strip()
        if not query:
            return (
                history,
                "### Quellen\nNoch keine Quellen vorhanden.",
                [],
                {},
                ("Bitte eine Anfrage eingeben."),
            )
        history.append({"role": "user", "content": query})
        started = time.perf_counter()
        try:
            answer, route, trace = self.flow_runner(query)
            if route is None:
                raise RuntimeError("Workflow completed without a route.")
            source_ids = sorted(set(SOURCE_PATTERN.findall(answer)))
            sources = (
                "### Quellen\n" + "\n".join(f"- `{source_id}`" for source_id in source_ids)
                if source_ids
                else "### Quellen\nIn der generierten Antwort wurde keine Quellen-ID genannt."
            )
            trace_rows = [
                [
                    event.timestamp.isoformat(),
                    TRACE_EVENT_LABELS.get(event.event, event.event),
                    _trace_detail(event.event, event.detail),
                ]
                for event in trace
            ]
            trace_details = {event.event: event.detail for event in trace}
            tools = {
                "Anfragetyp": _ui_value(route.intent.value),
                "Fall-ID": route.case_id,
                "Modellprofil": _ui_value(trace_details.get("model_profile", "not recorded")),
                "MCP-Werkzeuge": route.required_tools,
                "Ausführungsmodus": _ui_value(trace_details.get("execution_mode", "not recorded")),
            }
            if "configured_complex_model" in trace_details:
                tools["Konfiguriertes komplexes Modell"] = trace_details["configured_complex_model"]
                tools["Modus für vollständige Prüfung"] = _ui_value(
                    trace_details.get("full_assessment_mode", "not recorded")
                )
            else:
                tools["Ausgewähltes Modell"] = trace_details.get("model_selected", "nicht erfasst")
            if "fallback_reason" in trace_details:
                tools["Fallback-Grund"] = _trace_detail(
                    "fallback_reason", trace_details["fallback_reason"]
                )
            if "Konfiguriertes komplexes Modell" in tools:
                status = (
                    f"Abgeschlossen als `{tools['Anfragetyp']}` über "
                    f"`{tools['Modus für vollständige Prüfung']}` im Modus "
                    f"`{tools['Ausführungsmodus']}`. Das konfigurierte Modell "
                    f"`{tools['Konfiguriertes komplexes Modell']}` wurde nicht ausgeführt; "
                    f"{len(trace_rows)} technische Ereignisse."
                )
            else:
                status = (
                    f"Abgeschlossen als `{tools['Anfragetyp']}` mit "
                    f"`{tools['Ausgewähltes Modell']}` im Modus "
                    f"`{tools['Ausführungsmodus']}`; {len(trace_rows)} technische Ereignisse."
                )
            logger.info(
                "request_completed",
                extra={
                    "intent": route.intent.value,
                    "execution_mode": trace_details.get("execution_mode"),
                    "query_length": len(query),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
        except UnsafeInputError as exc:
            logger.info("request_blocked", extra={"query_length": len(query)})
            answer = (
                "Diese Anfrage wurde aus Sicherheitsgründen nicht ausgeführt. "
                f"{exc} Bitte formuliere eine fachliche Frage zu Richtlinien oder "
                "einem synthetischen Fall."
            )
            sources = "### Quellen\nKeine Quellen – die Anfrage wurde blockiert."
            trace_rows = []
            tools = {}
            status = "Anfrage blockiert."
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "query_length": len(query),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            answer = (
                "Der lokale Ablauf konnte nicht abgeschlossen werden. Prüfe, ob Ollama läuft "
                "und das konfigurierte Modell installiert ist, und versuche es erneut."
            )
            sources = "### Quellen\nKeine Quellen – der Ablauf wurde nicht abgeschlossen."
            trace_rows = []
            tools = {}
            status = "Ablauf nicht verfügbar; vertrauliche Fehlerdetails wurden nicht ausgegeben."
        history.append({"role": "assistant", "content": answer})
        return history, sources, trace_rows, tools, status

    def case_view(self, case_id: str) -> dict[str, Any]:
        """Return a structured case view for the non-agent browse tab."""
        case_data = self.tools.get_customer_case(case_id).model_dump(mode="json")
        view = _ui_value(case_data)
        if not isinstance(view, dict):
            raise TypeError("Case view must be a mapping.")
        return view

    def diagnostics(self) -> dict[str, Any]:
        """Check local components without sending enterprise data externally."""
        settings = get_settings()
        ollama = "nicht verfügbar"
        try:
            response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.0)
            ollama = "verfügbar" if response.is_success else f"HTTP {response.status_code}"
        except httpx.HTTPError:
            pass
        try:
            registered = asyncio.run(create_mcp_server(self.tools).list_tools())
            mcp_tools = sorted(tool.name for tool in registered)
        except Exception:
            mcp_tools = []
        return {
            "Umgebung": _ui_value(settings.app_env),
            "Ollama": ollama,
            "Schnelles lokales Modell": settings.ollama_fast_model,
            "Komplexes agentisches Modell": settings.ollama_complex_model,
            "Modus für vollständige Prüfung": _ui_value(settings.full_assessment_mode),
            "MCP-Status": "bereit" if len(mcp_tools) == 4 else "nicht verfügbar",
            "MCP-Werkzeuge": mcp_tools,
            "Synthetische Fälle": len(self.tools.repository.list_cases()),
            "Dokumente in der Wissensbasis": len(self.tools.knowledge_service.document_ids()),
            "Externe Cloud erforderlich": "Nein",
        }


def build_app(controller: AssistantController | None = None) -> gr.Blocks:
    """Build the enterprise-oriented Blocks application without launching it."""
    controller = controller or AssistantController()
    case_ids = [case.case_id for case in controller.tools.repository.list_cases()]
    document_count = len(controller.tools.knowledge_service.document_ids())

    app = gr.Blocks(title=UI_TITLE)
    with app:
        gr.HTML(
            f"<div class='hero'><h1>{UI_TITLE}</h1>"
            f"<p>{COMPANY_NAME} · Lokale agentische Entscheidungsunterstützung</p></div>"
        )
        gr.Markdown(f"> **Synthetische Demo:** {UI_DISCLAIMER}")

        with gr.Tabs():
            with gr.Tab("Assistent"):
                chatbot = gr.Chatbot(
                    value=[
                        {
                            "role": "assistant",
                            "content": (
                                "Bereit für Fragen zu synthetischen NovaBank-Richtlinien und "
                                "Kreditfällen. Sämtliche Fachfunktionen werden über MCP aufgerufen."
                            ),
                        }
                    ],
                    label="Assistent",
                    height=420,
                    layout="panel",
                    placeholder="Frage nach Richtlinien oder einem synthetischen CASE-00000.",
                )
                with gr.Row():
                    prompt = gr.Textbox(
                        label="Anfrage",
                        placeholder="Prüfe CASE-00031 vollständig …",
                        lines=2,
                        scale=5,
                    )
                    submit = gr.Button("Prüfung starten", variant="primary", scale=1)
                gr.Markdown(
                    "**Demo-Szenarien**  \n"
                    "`Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?`  \n"
                    "`Zeige CASE-00001.`  \n"
                    "`Berechne die Kreditbelastung für CASE-00001.`  \n"
                    "`Welche Compliance-Probleme hat CASE-00017?`  \n"
                    "`Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage.`"
                )
                run_status = gr.Markdown("Bereit.", elem_classes="status-card")
                with gr.Row():
                    sources = gr.Markdown("### Quellen\nNoch keine Quellen vorhanden.")
                    tools_used = gr.JSON(label="Routing, Modell und MCP-Werkzeuge")
                trace = gr.Dataframe(
                    headers=["Zeitstempel", "Ereignis", "Details"],
                    datatype=["str", "str", "str"],
                    label="Ausführungsprotokoll (nur technische Ereignisse)",
                    interactive=False,
                )
                submit.click(
                    controller.submit,
                    inputs=[prompt, chatbot],
                    outputs=[chatbot, sources, trace, tools_used, run_status],
                )
                prompt.submit(
                    controller.submit,
                    inputs=[prompt, chatbot],
                    outputs=[chatbot, sources, trace, tools_used, run_status],
                )

            with gr.Tab("Fälle"):
                gr.Markdown(
                    "Validierte synthetische Datensätze durchsuchen, ohne ein Sprachmodell "
                    "aufzurufen."
                )
                case_selector = gr.Dropdown(
                    case_ids, value="CASE-00001", label="Synthetischer Fall"
                )
                case_json = gr.JSON(value=controller.case_view("CASE-00001"), label="Falldaten")
                case_selector.change(controller.case_view, inputs=case_selector, outputs=case_json)

            with gr.Tab("Wissensbasis & Dokumente"):
                gr.Markdown(
                    f"Das Repository enthält {document_count} synthetische, versionierte "
                    "interne Richtlinien. "
                    "Suchergebnisse bewahren Metadaten zu Dokument, Abschnitt, Version, "
                    "Verantwortlichen und Seite."
                )
                gr.Markdown(
                    "Zentrale Kontrollgrundlagen: `NB-CRD-001`, `NB-KYC-001`, `NB-DOC-001`, "
                    "`NB-RSK-001` und `NB-SEC-001`."
                )

            with gr.Tab("System / Diagnose"):
                gr.Markdown(
                    "Systemprüfungen bleiben lokal. Es werden keine Fallinhalte an externe "
                    "Dienste gesendet."
                )
                diagnostic_output = gr.JSON(label="Lokaler Systemstatus")
                diagnostic_button = gr.Button("Diagnose starten")
                diagnostic_button.click(controller.diagnostics, outputs=diagnostic_output)

    return app


def main() -> None:
    """Launch on loopback only with sharing disabled."""
    settings = get_settings()
    configure_logging(settings.log_level)
    build_app().launch(
        server_name=settings.ui_server_name,
        server_port=settings.ui_server_port,
        share=False,
        show_error=False,
        css=CSS,
        js=GRADIO_UI_LOCALIZATION_JS,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
