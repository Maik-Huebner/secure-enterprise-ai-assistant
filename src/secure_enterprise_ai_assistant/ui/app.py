"""Professional Gradio Blocks interface for the local NovaBank assistant."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any

import gradio as gr
import httpx

from secure_enterprise_ai_assistant.core.company import COMPANY_NAME, PROJECT_DISCLAIMER
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.flows import NovaBankAssistantFlow
from secure_enterprise_ai_assistant.mcp import create_mcp_server
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService

SOURCE_PATTERN = re.compile(r"\bNB-[A-Z]+-\d{3}\b")

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
        flow = NovaBankAssistantFlow()
        answer = str(flow.kickoff(inputs={"query": query}))
        return answer, flow.state.route, flow.state.trace

    def submit(
        self, message: str, history: list[dict[str, str]] | None
    ) -> tuple[list[dict[str, str]], str, list[list[str]], dict[str, Any], str]:
        """Execute a Flow and return chat, sources, trace, tools, and status."""
        history = list(history or [])
        query = message.strip()
        if not query:
            return history, "No sources.", [], {}, "Enter a request."
        history.append({"role": "user", "content": query})
        try:
            answer, route, trace = self.flow_runner(query)
            if route is None:
                raise RuntimeError("Workflow completed without a route.")
            source_ids = sorted(set(SOURCE_PATTERN.findall(answer)))
            sources = (
                "\n".join(f"- `{source_id}`" for source_id in source_ids)
                if source_ids
                else "No source ID was cited in the generated response."
            )
            trace_rows = [
                [event.timestamp.isoformat(), event.event, event.detail] for event in trace
            ]
            trace_details = {event.event: event.detail for event in trace}
            tools = {
                "intent": route.intent.value,
                "case_id": route.case_id,
                "model": trace_details.get("model_selected", "not recorded"),
                "model_profile": trace_details.get("model_profile", "not recorded"),
                "mcp_tools": route.required_tools,
                "execution_mode": trace_details.get("execution_mode", "not recorded"),
            }
            if "fallback_reason" in trace_details:
                tools["fallback_reason"] = trace_details["fallback_reason"]
            status = (
                f"Completed via `{route.intent.value}` using "
                f"`{tools['model']}` in `{tools['execution_mode']}` mode; "
                f"{len(trace_rows)} technical trace events."
            )
        except Exception:
            answer = (
                "The local workflow could not complete. Verify that Ollama is running "
                "and that the configured model is installed, then retry."
            )
            sources = "No sources — workflow did not complete."
            trace_rows = []
            tools = {}
            status = "Workflow unavailable; no sensitive exception details were exposed."
        history.append({"role": "assistant", "content": answer})
        return history, sources, trace_rows, tools, status

    def case_view(self, case_id: str) -> dict[str, Any]:
        """Return a structured case view for the non-agent browse tab."""
        return self.tools.get_customer_case(case_id).model_dump(mode="json")

    def diagnostics(self) -> dict[str, Any]:
        """Check local components without sending enterprise data externally."""
        settings = get_settings()
        ollama = "unavailable"
        try:
            response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.0)
            ollama = "available" if response.is_success else f"HTTP {response.status_code}"
        except httpx.HTTPError:
            pass
        try:
            registered = asyncio.run(create_mcp_server(self.tools).list_tools())
            mcp_tools = sorted(tool.name for tool in registered)
        except Exception:
            mcp_tools = []
        return {
            "environment": settings.app_env,
            "ollama": ollama,
            "ollama_fast_model": settings.ollama_fast_model,
            "ollama_complex_model": settings.ollama_complex_model,
            "mcp_status": "ready" if len(mcp_tools) == 4 else "unavailable",
            "mcp_tools": mcp_tools,
            "synthetic_cases": len(self.tools.repository.list_cases()),
            "knowledge_documents": 18,
            "external_cloud_required": False,
        }


def build_app(controller: AssistantController | None = None) -> gr.Blocks:
    """Build the enterprise-oriented Blocks application without launching it."""
    controller = controller or AssistantController()
    case_ids = [case.case_id for case in controller.tools.repository.list_cases()]

    with gr.Blocks(title="Secure Enterprise AI Assistant") as app:
        gr.HTML(
            f"<div class='hero'><h1>Secure Enterprise AI Assistant</h1>"
            f"<p>{COMPANY_NAME} · Local-first agentic decision support</p></div>"
        )
        gr.Markdown(f"> **Synthetic demo:** {PROJECT_DISCLAIMER}")

        with gr.Tabs():
            with gr.Tab("Assistant"):
                chatbot = gr.Chatbot(
                    value=[
                        {
                            "role": "assistant",
                            "content": (
                                "Ready for synthetic NovaBank policy and credit-case "
                                "questions. Every business capability is accessed through MCP."
                            ),
                        }
                    ],
                    label="Assistant",
                    height=420,
                    layout="panel",
                    placeholder="Ask about policies or a synthetic CASE-00000 record.",
                )
                with gr.Row():
                    prompt = gr.Textbox(
                        label="Request",
                        placeholder="Prüfe CASE-00031 vollständig …",
                        lines=2,
                        scale=5,
                    )
                    submit = gr.Button("Run secure workflow", variant="primary", scale=1)
                gr.Examples(
                    examples=[
                        ["Welche Unterlagen benötigt NovaBank für einen Konsumentenkredit?"],
                        ["Zeige CASE-00001."],
                        ["Berechne die Kreditbelastung für CASE-00001."],
                        ["Welche Compliance-Probleme hat CASE-00017?"],
                        ["Prüfe CASE-00031 vollständig und erstelle eine Entscheidungsvorlage."],
                    ],
                    inputs=prompt,
                    label="Demo scenarios",
                )
                run_status = gr.Markdown("Ready.", elem_classes="status-card")
                with gr.Row():
                    sources = gr.Markdown("No sources yet.")
                    tools_used = gr.JSON(label="Routing, model and MCP tools")
                trace = gr.Dataframe(
                    headers=["Timestamp", "Event", "Detail"],
                    datatype=["str", "str", "str"],
                    label="Execution trace (technical events only)",
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

            with gr.Tab("Cases"):
                gr.Markdown("Browse validated synthetic records without invoking an LLM.")
                case_selector = gr.Dropdown(case_ids, value="CASE-00001", label="Synthetic case")
                case_json = gr.JSON(value=controller.case_view("CASE-00001"), label="Case data")
                case_selector.change(controller.case_view, inputs=case_selector, outputs=case_json)

            with gr.Tab("Knowledge & Documents"):
                gr.Markdown(
                    "The repository contains 18 synthetic, versioned internal policies. "
                    "Search results retain document, section, version, owner, and page metadata."
                )
                gr.Markdown(
                    "Key controls: `NB-CRD-001`, `NB-KYC-001`, `NB-DOC-001`, "
                    "`NB-RSK-001`, and `NB-SEC-001`."
                )

            with gr.Tab("System / Diagnostics"):
                gr.Markdown(
                    "Health checks remain local. No case content is sent to an external service."
                )
                diagnostic_output = gr.JSON(label="Local system status")
                diagnostic_button = gr.Button("Run diagnostics")
                diagnostic_button.click(controller.diagnostics, outputs=diagnostic_output)

    return app


def main() -> None:
    """Launch on loopback only with sharing disabled."""
    settings = get_settings()
    build_app().launch(
        server_name=settings.ui_server_name,
        server_port=settings.ui_server_port,
        share=False,
        show_error=False,
        css=CSS,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
