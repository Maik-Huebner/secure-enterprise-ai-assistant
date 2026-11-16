"""Gradio interface for the NovaBank assistant. It is a client of the REST API.

The UI holds no business logic and no direct access to cases, documents or tools: it logs in
at the API, keeps the short-lived token in the per-browser session state, and sends every
request with that token. Authorization happens in the API and in the MCP tools.
"""

from __future__ import annotations

import re
import time
from typing import Any

import gradio as gr

from secure_enterprise_ai_assistant.core.company import COMPANY_NAME, PROJECT_DISCLAIMER
from secure_enterprise_ai_assistant.core.labels import CODE_LABELS
from secure_enterprise_ai_assistant.core.logs import configure_logging, get_logger, request_context
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.models.orchestration import TraceEvent
from secure_enterprise_ai_assistant.ui.api_client import ApiClient, ApiError

SOURCE_PATTERN = re.compile(r"\bNB-[A-Z]+-\d{3}\b")
logger = get_logger(__name__)

UI_TITLE = "Sicherer Enterprise-KI-Assistent"
UI_DISCLAIMER = PROJECT_DISCLAIMER

TRACE_EVENT_LABELS = {
    "request_received": "Anfrage empfangen",
    "intent_classified": "Anfragetyp erkannt",
    "routing_method": "Erkennungsmethode",
    "model_selected": "Modell ausgewählt",
    "tools_selected": "MCP-Werkzeuge ausgeführt",
    "answer_verification": "Antwortprüfung",
    "answer_retry": "Erneuter Versuch",
    "fallback_reason": "Grund für den Rückfallweg",
    "approval_requested": "Freigabe angefordert",
    "approval_decision": "Freigabeentscheidung",
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
    "llm_grounded": "Sprachmodell mit geprüften Nachweisen",
    "verified_fallback": "Verifizierter Rückfallweg (ohne Sprachmodell)",
    "verified_mcp": "Verifizierter MCP-Pfad (ohne Sprachmodell)",
    "no_answer": "Keine passende Quelle",
    "completed": "abgeschlossen",
    "awaiting_approval": "wartet auf Freigabe",
    "approved": "freigegeben",
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


Session = dict[str, Any]
EMPTY_SOURCES = "### Quellen\nNoch keine Quellen vorhanden."
ROLE_LABELS = {"sachbearbeiter": "Sachbearbeitung", "pruefer": "Prüfung", "admin": "Administration"}


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
    return str(_ui_value(detail))


class AssistantController:
    """UI adapter: talks only to the API and never shows internal exception details."""

    def __init__(self, api: ApiClient | None = None) -> None:
        self.api = api or ApiClient(get_settings().api_base_url)

    # ----- session ---------------------------------------------------------------------------
    def login(self, username: str, password: str) -> tuple[Session, str, Any]:
        """Log in at the API; return the new session, a status line and the case choices."""
        try:
            token = self.api.login(username.strip(), password)
            me = self.api.me(token)
            cases = [item["case_id"] for item in self.api.cases(token)]
        except ApiError as exc:
            return {}, f"**Anmeldung fehlgeschlagen:** {exc}", gr.update(choices=[], value=None)
        session = {"token": token, "username": me["username"], "role": me["role"]}
        role = ROLE_LABELS.get(me["role"], me["role"])
        team = f", {me['team']}" if me.get("team") else ""
        status = f"Angemeldet als **{me['username']}** ({role}{team}). {len(cases)} Fälle sichtbar."
        return session, status, gr.update(choices=cases, value=cases[0] if cases else None)

    @staticmethod
    def logout() -> tuple[Session, str, Any]:
        return {}, "Abgemeldet.", gr.update(choices=[], value=None)

    # ----- assistant -------------------------------------------------------------------------
    def submit(
        self, message: str, history: list[dict[str, str]] | None, session: Session | None
    ) -> tuple[list[dict[str, str]], str, list[list[str]], dict[str, Any], str]:
        """Send one request to the API; return chat, sources, trace, routing info and status."""
        with request_context():
            return self._submit(message, list(history or []), session or {})

    def _submit(
        self, message: str, history: list[dict[str, str]], session: Session
    ) -> tuple[list[dict[str, str]], str, list[list[str]], dict[str, Any], str]:
        query = message.strip()
        if not query:
            return history, EMPTY_SOURCES, [], {}, "Bitte eine Anfrage eingeben."
        if not session.get("token"):
            return history, EMPTY_SOURCES, [], {}, "Bitte zuerst anmelden."
        history.append({"role": "user", "content": query})
        started = time.perf_counter()
        try:
            result = self.api.chat(session["token"], query)
        except ApiError as exc:
            logger.info(
                "ui_request_failed", extra={"status": exc.status, "query_length": len(query)}
            )
            if exc.status in {400, 403, 401, 429}:
                answer = f"Diese Anfrage wurde nicht ausgeführt. {exc}"
            else:
                answer = (
                    "Der Ablauf konnte nicht abgeschlossen werden. Prüfe, ob API und Ollama "
                    "laufen, und versuche es erneut."
                )
            history.append({"role": "assistant", "content": answer})
            return history, "### Quellen\nKeine Quellen.", [], {}, "Anfrage nicht ausgeführt."

        trace = [TraceEvent.model_validate(item) for item in result["trace"]]
        details = {event.event: event.detail for event in trace}
        sources = (
            "### Quellen\n" + "\n".join(f"- `{source}`" for source in result["sources"])
            if result["sources"]
            else "### Quellen\nIn der Antwort wurde keine Quellen-ID genannt."
        )
        trace_rows = [
            [
                event.timestamp.isoformat(),
                TRACE_EVENT_LABELS.get(event.event, event.event),
                _trace_detail(event.event, event.detail),
            ]
            for event in trace
        ]
        info: dict[str, Any] = {
            "Status": _ui_value(result["status"]),
            "Anfragetyp": _ui_value(result["intent"]),
            "Fall-ID": result["case_id"],
            "Erkennungsmethode": _ui_value(result["routing_method"]),
            "Ausführungsmodus": _ui_value(result["execution_mode"] or "not recorded"),
            "Modell": details.get("model_selected", "nicht verwendet"),
            "Antwortprüfung": details.get("answer_verification", "nicht nötig"),
        }
        if "fallback_reason" in details:
            info["Grund für den Rückfallweg"] = details["fallback_reason"]
        if result["status"] == "awaiting_approval":
            status = (
                f"Entscheidungsvorlage für `{result['case_id']}` erstellt. Sie wartet auf die "
                "Freigabe durch eine zweite prüfende Person (Reiter »Freigaben«)."
            )
        else:
            status = (
                f"Abgeschlossen als `{info['Anfragetyp']}` im Modus `{info['Ausführungsmodus']}`; "
                f"{len(trace_rows)} technische Ereignisse."
            )
        logger.info(
            "ui_request_completed",
            extra={
                "intent": result["intent"],
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        history.append({"role": "assistant", "content": result["answer"]})
        return history, sources, trace_rows, info, status

    # ----- approvals ---------------------------------------------------------------------------
    def load_reviews(self, session: Session | None) -> tuple[Any, str]:
        """Open approvals for reviewers."""
        token = (session or {}).get("token")
        if not token:
            return gr.update(choices=[], value=None), "Bitte zuerst anmelden."
        try:
            reviews = self.api.reviews(token)
        except ApiError as exc:
            return gr.update(choices=[], value=None), str(exc)
        choices = [
            (f"{item['case_id']} – angefordert von {item['requested_by']}", item["thread_id"])
            for item in reviews
        ]
        return (
            gr.update(choices=choices, value=choices[0][1] if choices else None),
            f"{len(choices)} offene Freigaben." if choices else "Keine offenen Freigaben.",
        )

    def show_review(self, thread_id: str | None, session: Session | None) -> str:
        token = (session or {}).get("token")
        if not thread_id or not token:
            return ""
        try:
            return str(self.api.review(token, thread_id)["draft"])
        except ApiError as exc:
            return f"**Hinweis:** {exc}"

    def decide(
        self, thread_id: str | None, comment: str, approve: bool, session: Session | None
    ) -> tuple[str, str]:
        token = (session or {}).get("token")
        if not thread_id or not token:
            return "", "Bitte zuerst eine offene Freigabe auswählen."
        try:
            result = self.api.decide(token, thread_id, "approve" if approve else "reject", comment)
        except ApiError as exc:
            return "", f"**Nicht ausgeführt:** {exc}"
        verdict = "freigegeben" if approve else "abgelehnt"
        return str(result["answer"]), f"Entscheidungsvorlage {verdict}."

    # ----- cases and diagnostics -------------------------------------------------------------
    def case_view(self, case_id: str | None, session: Session | None) -> dict[str, Any]:
        """Return a structured, German-labelled case view (data comes from the API)."""
        if not case_id or not (session or {}).get("token"):
            return {}
        try:
            view = _ui_value(self.api.case(session["token"], case_id))  # type: ignore[index]
        except ApiError as exc:
            return {"Hinweis": str(exc)}
        return view if isinstance(view, dict) else {}

    def diagnostics(self) -> dict[str, Any]:
        """Readiness of API, search index and Ollama, without sending case data anywhere."""
        settings = get_settings()
        try:
            ready = self.api.ready()
            api_status = "erreichbar"
            checks = ready["checks"]
        except ApiError:
            api_status, checks = "nicht erreichbar", {}
        return {
            "API": api_status,
            "API-Adresse": settings.api_base_url,
            "Suchindex": "bereit" if checks.get("knowledge_index") else "nicht bereit",
            "Ollama": "verfügbar" if checks.get("ollama") else "nicht verfügbar",
            "Sprachmodell": settings.ollama_fast_model,
            "Embedding-Modell": settings.embedding_model,
            "Umgebung": _ui_value(settings.app_env),
            "Externe Cloud erforderlich": "Nein",
        }


def build_app(controller: AssistantController | None = None) -> gr.Blocks:
    """Build the Blocks application without launching it."""
    controller = controller or AssistantController()
    app = gr.Blocks(title=UI_TITLE)
    with app:
        session = gr.State({})
        gr.HTML(
            f"<div class='hero'><h1>{UI_TITLE}</h1>"
            f"<p>{COMPANY_NAME} · Lokale agentische Entscheidungsunterstützung</p></div>"
        )
        gr.Markdown(f"> **Synthetische Demo:** {UI_DISCLAIMER}")
        with gr.Row():
            username = gr.Textbox(label="Benutzername", scale=2)
            password = gr.Textbox(label="Passwort", type="password", scale=2)
            login_button = gr.Button("Anmelden", variant="primary", scale=1)
            logout_button = gr.Button("Abmelden", scale=1)
        login_status = gr.Markdown("Nicht angemeldet.", elem_classes="status-card")

        with gr.Tabs():
            with gr.Tab("Assistent"):
                chatbot = gr.Chatbot(
                    value=[
                        {
                            "role": "assistant",
                            "content": (
                                "Bereit für Fragen zu synthetischen NovaBank-Richtlinien und "
                                "Kreditfällen. Alle Fachfunktionen laufen über die API und MCP."
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
                    sources = gr.Markdown(EMPTY_SOURCES)
                    tools_used = gr.JSON(label="Routing, Modell und MCP-Werkzeuge")
                trace = gr.Dataframe(
                    headers=["Zeitstempel", "Ereignis", "Details"],
                    datatype=["str", "str", "str"],
                    label="Ausführungsprotokoll (nur technische Ereignisse)",
                    interactive=False,
                )
                outputs = [chatbot, sources, trace, tools_used, run_status]
                submit.click(controller.submit, inputs=[prompt, chatbot, session], outputs=outputs)
                prompt.submit(controller.submit, inputs=[prompt, chatbot, session], outputs=outputs)

            with gr.Tab("Fälle"):
                gr.Markdown(
                    "Validierte synthetische Datensätze, die du sehen darfst – ohne Sprachmodell."
                )
                case_selector = gr.Dropdown([], label="Synthetischer Fall")
                case_json = gr.JSON(label="Falldaten")
                case_selector.change(
                    controller.case_view, inputs=[case_selector, session], outputs=case_json
                )

            with gr.Tab("Freigaben"):
                gr.Markdown(
                    "Entscheidungsvorlagen werden erst nach Freigabe durch eine **zweite** "
                    "Prüferin oder einen zweiten Prüfer wirksam (Vier-Augen-Prinzip)."
                )
                with gr.Row():
                    load_button = gr.Button("Offene Freigaben laden")
                    review_selector = gr.Dropdown([], label="Offene Freigabe", scale=3)
                review_status = gr.Markdown("")
                review_draft = gr.Markdown("")
                review_comment = gr.Textbox(label="Kommentar (optional)", lines=2)
                with gr.Row():
                    approve_button = gr.Button("Freigeben", variant="primary")
                    reject_button = gr.Button("Ablehnen", variant="stop")
                load_button.click(
                    controller.load_reviews,
                    inputs=[session],
                    outputs=[review_selector, review_status],
                )
                review_selector.change(
                    controller.show_review, inputs=[review_selector, session], outputs=review_draft
                )
                approve_button.click(
                    lambda thread, comment, state: controller.decide(thread, comment, True, state),
                    inputs=[review_selector, review_comment, session],
                    outputs=[review_draft, review_status],
                )
                reject_button.click(
                    lambda thread, comment, state: controller.decide(thread, comment, False, state),
                    inputs=[review_selector, review_comment, session],
                    outputs=[review_draft, review_status],
                )

            with gr.Tab("Wissensbasis & Dokumente"):
                gr.Markdown(
                    "Die Wissensbasis enthält synthetische, versionierte interne Richtlinien. "
                    "Welche du durchsuchen darfst, hängt von deiner Rolle ab: vertrauliche "
                    "Dokumente (z. B. `NB-AML-001`) sehen nur Prüferinnen, Prüfer und Admins."
                )
                gr.Markdown(
                    "Zentrale Kontrollgrundlagen: `NB-CRD-001`, `NB-KYC-001`, `NB-DOC-001` und "
                    "`NB-RSK-001`."
                )

            with gr.Tab("System / Diagnose"):
                gr.Markdown(
                    "Systemprüfungen bleiben lokal. Es werden keine Fallinhalte an externe "
                    "Dienste gesendet."
                )
                diagnostic_output = gr.JSON(label="Lokaler Systemstatus")
                diagnostic_button = gr.Button("Diagnose starten")
                diagnostic_button.click(controller.diagnostics, outputs=diagnostic_output)

        login_button.click(
            controller.login,
            inputs=[username, password],
            outputs=[session, login_status, case_selector],
        )
        logout_button.click(controller.logout, outputs=[session, login_status, case_selector])
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
