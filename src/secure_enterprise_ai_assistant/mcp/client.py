"""MCP client used by the LangGraph tool node, and the deterministic decision-brief renderer.

The graph never lets the language model choose tools: the router fixes the tool plan, and this
client executes exactly that plan in one MCP session (stdio subprocess or Streamable HTTP) with
the caller's short-lived MCP token.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import httpx2
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from secure_enterprise_ai_assistant.core.labels import format_eur, format_pct, label
from secure_enterprise_ai_assistant.core.language import REPORT_END_MARKER
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.mcp.environment import server_environment
from secure_enterprise_ai_assistant.models.orchestration import QueryIntent, RouteDecision
from secure_enterprise_ai_assistant.security import AccessDeniedError
from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError

MCP_MODULE = "secure_enterprise_ai_assistant.mcp.server"
# Kept in sync with mcp.server.ACCESS_TOKEN_VARIABLE (not imported to avoid a cycle).
ACCESS_TOKEN_VARIABLE = "NOVABANK_ACCESS_TOKEN"
EVIDENCE_KEYS = {
    "get_customer_case": "case",
    "analyze_financial_case": "financial",
    "check_compliance": "compliance",
    "search_internal_knowledge": "knowledge",
}
RECOMMENDATION_LABELS = {
    "approve": "Genehmigungskandidat",
    "manual_review": "Manuelle Prüfung",
    "decline": "Ablehnung",
}

Evidence = dict[str, dict[str, Any]]


class MCPClientError(RuntimeError):
    """Raised when the local MCP server returns unusable structured output."""


def knowledge_query_for(failed_messages: list[str]) -> str:
    """Build the German policy-evidence query for compliance and full assessments."""
    base = (
        "Richtlinien zu Schuldendienstquote, Tragfähigkeit, Pflichtunterlagen, KYC, "
        "Risikoklasse und Entscheidungskontrollen"
    )
    return " ".join([base, *failed_messages])[:900]


MAX_RULE_SOURCES = 3
MAX_PASSAGES = 7


def knowledge_requests(
    route: RouteDecision, query: str, evidence: Evidence
) -> list[dict[str, Any]]:
    """Search calls for one route: the question itself, or the failed rules' own sources first."""
    if route.intent == QueryIntent.KNOWLEDGE:
        return [{"question": query, "top_k": 5}]
    failed = [
        finding
        for finding in evidence.get("compliance", {}).get("findings", [])
        if not finding.get("passed", False)
    ]
    requests: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in failed:
        document_id = finding.get("source_document_id")
        if document_id and document_id not in seen and len(seen) < MAX_RULE_SOURCES:
            seen.add(document_id)
            question = f"{finding.get('source_section', '')} {finding.get('message', '')}"
            requests.append({"question": question[:900], "top_k": 2, "document_id": document_id})
    messages = [str(finding.get("message", "")) for finding in failed]
    requests.append({"question": knowledge_query_for(messages), "top_k": 5})
    return requests


def merge_knowledge(responses: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge several search responses; rule sources first, duplicates removed."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for response in responses:
        if response.get("out_of_scope"):
            continue
        for result in response.get("results", []):
            chunk_id = result["chunk"]["chunk_id"]
            if chunk_id not in seen:
                seen.add(chunk_id)
                results.append(result)
    query = responses[-1].get("query", "") if responses else ""
    return {"query": query, "results": results[:MAX_PASSAGES], "out_of_scope": not results}


def _error_text(result: CallToolResult) -> str:
    return " ".join(item.text for item in result.content if isinstance(item, TextContent))


def _raise_for(tool: str, result: CallToolResult) -> None:
    text = _error_text(result)
    if "Unbekannte synthetische Fall-ID" in text:
        raise CaseNotFoundError(text.split(": ", 1)[-1] if ": " in text else text)
    if "Anmeldung nötig" in text or "Berechtigung" in text:
        raise AccessDeniedError("Für diese Anfrage fehlt die Berechtigung.")
    raise MCPClientError(f"Das MCP-Werkzeug {tool} lieferte keine strukturierten Daten.")


class McpEvidenceClient:
    """Executes the router's tool plan over MCP (stdio or Streamable HTTP) for one caller."""

    def __init__(
        self,
        access_token: str | None,
        timeout_seconds: int | None = None,
        transport: str | None = None,
        server_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._access_token = access_token
        self.timeout_seconds = timeout_seconds or settings.mcp_request_timeout_seconds
        self.transport = transport or settings.mcp_transport
        self.server_url = server_url or settings.mcp_server_url

    def collect(self, route: RouteDecision, query: str) -> Evidence:
        """Return structured results keyed by 'case', 'financial', 'compliance', 'knowledge'."""
        try:
            return asyncio.run(asyncio.wait_for(self._collect(route, query), self.timeout_seconds))
        except TimeoutError as exc:
            raise MCPClientError(
                f"Die MCP-Abfrage hat das Zeitlimit von {self.timeout_seconds} s überschritten."
            ) from exc

    async def _collect(self, route: RouteDecision, query: str) -> Evidence:
        if self.transport == "http":
            return await self._collect_http(route, query)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", MCP_MODULE],
            env=server_environment(
                {ACCESS_TOKEN_VARIABLE: self._access_token} if self._access_token else None
            ),
        )
        try:
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await run_tool_plan(session, route, query)
        except BaseExceptionGroup as group:
            # MCP 2.x runs the transport in a task group: domain errors arrive wrapped.
            _raise_domain_error(group)
            raise MCPClientError("Der MCP-Server hat die Anfrage nicht beantwortet.") from group

    async def _collect_http(self, route: RouteDecision, query: str) -> Evidence:
        headers = {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}
        statuses: list[int] = []

        async def remember_status(response: httpx2.Response) -> None:
            # The MCP transport turns a 401 into a generic protocol error; keep the status.
            statuses.append(response.status_code)

        try:
            async with httpx2.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                event_hooks={"response": [remember_status]},
            ) as http:
                async with streamable_http_client(self.server_url, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        return await run_tool_plan(session, route, query)
        except BaseExceptionGroup as group:
            if {401, 403} & set(statuses):
                raise AccessDeniedError("Für diese Anfrage fehlt die Berechtigung.") from group
            _raise_domain_error(group)
            raise MCPClientError("Der MCP-HTTP-Server ist nicht erreichbar.") from group
        except httpx2.TransportError as exc:
            raise MCPClientError("Der MCP-HTTP-Server ist nicht erreichbar.") from exc


def _raise_domain_error(group: BaseExceptionGroup[BaseException]) -> None:
    """Re-raise the first expected error hidden in a task-group exception, if any."""
    for error in _leaves(group):
        if isinstance(error, (CaseNotFoundError, AccessDeniedError, MCPClientError)):
            raise error from None


def _leaves(group: BaseExceptionGroup[BaseException]) -> list[BaseException]:
    errors: list[BaseException] = []
    for error in group.exceptions:
        errors.extend(_leaves(error) if isinstance(error, BaseExceptionGroup) else [error])
    return errors


async def run_tool_plan(session: ClientSession, route: RouteDecision, query: str) -> Evidence:
    """Call exactly the router's tools in one MCP session; the model chooses nothing here."""
    evidence: Evidence = {}
    for tool in route.required_tools:
        if tool == "search_internal_knowledge":
            responses = []
            for arguments in knowledge_requests(route, query, evidence):
                result = await session.call_tool(tool, arguments)
                responses.append(_structured(tool, result))
            evidence["knowledge"] = merge_knowledge(responses)
            continue
        result = await session.call_tool(tool, {"case_id": route.case_id})
        evidence[EVIDENCE_KEYS[tool]] = _structured(tool, result)
    return evidence


def _structured(tool: str, result: object) -> dict[str, Any]:
    if not isinstance(result, CallToolResult):
        raise MCPClientError(f"Das MCP-Werkzeug {tool} lieferte keine strukturierten Daten.")
    if result.is_error or not isinstance(result.structured_content, dict):
        _raise_for(tool, result)
    return dict(result.structured_content or {})


def render_decision_brief(case_id: str, evidence: Evidence) -> str:
    """Render the decision brief only from structured MCP evidence (no language model)."""
    case = evidence["case"]["case"]
    customer = case["customer"]
    application = case["application"]
    metrics = evidence["financial"]["metrics"]
    findings = evidence["compliance"]["findings"]
    decision = evidence["compliance"]["decision"]
    finding_lines = [
        (
            f"- **{item['rule_id']}** ({label(item['severity'])}): "
            f"{'bestanden' if item['passed'] else 'nicht bestanden'} – {item['message']}"
        )
        for item in findings
    ]
    source_map: dict[str, tuple[str, str, str]] = {}
    for result in evidence["knowledge"].get("results", []):
        chunk = result["chunk"]
        source_map[chunk["document_id"]] = (chunk["title"], chunk["section"], chunk["version"])
    source_lines = [
        f"- **{document_id}** v{version} – {title}, Abschnitt {section}"
        for document_id, (title, section, version) in sorted(source_map.items())
    ] or ["- Keine ausreichend relevante Richtlinienquelle gefunden."]

    return "\n".join(
        [
            f"# Entscheidungsvorlage – {case_id}",
            "",
            "## Empfehlung",
            f"**Empfehlung: {RECOMMENDATION_LABELS[decision['recommendation']]}.** "
            f"{decision['rationale']}",
            "Diese Ausgabe ist Entscheidungsunterstützung; die endgültige Entscheidung trifft "
            "eine autorisierte prüfende Person.",
            "",
            "## Geprüfte Falldaten",
            f"- Synthetischer Kunde: {customer['full_name']} ({customer['customer_id']})",
            f"- Beschäftigung: {label(customer['employment_status'])}, "
            f"{customer['months_employed']} Monate",
            f"- KYC: {label(customer['kyc_status'])}; Risikoklasse: {customer['risk_class']}",
            f"- Antrag: {format_eur(application['requested_amount_eur'])} über "
            f"{application['term_months']} Monate zu "
            f"{format_pct(application['annual_interest_rate_pct'])} p. a.",
            "",
            "## Deterministische Finanzkennzahlen",
            f"- Monatliche Rate: **{format_eur(metrics['monthly_payment_eur'])}**",
            f"- DTI vor Kredit: **{format_pct(metrics['debt_to_income_before_pct'])}**",
            f"- DTI nach Kredit: **{format_pct(metrics['debt_to_income_after_pct'])}**",
            f"- Gesamtzins: **{format_eur(metrics['total_interest_eur'])}**",
            f"- Gesamtrückzahlung: **{format_eur(metrics['total_repayment_eur'])}**",
            "- Monatliche Verpflichtungen nach Kredit: "
            f"**{format_eur(metrics['monthly_obligations_after_eur'])}**",
            "",
            "Die Zahlen stammen unverändert aus `analyze_financial_case`; es wurde keine "
            "Arithmetik eines Sprachmodells verwendet.",
            "",
            "## Compliance- und Regelprüfung",
            *finding_lines,
            "",
            "## Geprüfte Quellen",
            *source_lines,
            "",
            "## Verwendete MCP-Werkzeuge",
            *[f"- `{name}`" for name in EVIDENCE_KEYS],
            "",
            "Alle Nachweise wurden in einer echten lokalen MCP-stdio-Sitzung abgerufen.",
            "",
            "## Hinweise für die prüfende Person",
            "Offene Warnungen sind vor einer Genehmigung nachvollziehbar zu entscheiden. "
            "Kritische harte Ablehnungsregeln dürfen nicht durch Text eines Sprachmodells "
            "überschrieben werden. Referenzlabels sind nicht Teil dieser Nachweise und wurden "
            "weder an das Modell noch an den Berichtsgenerator übergeben.",
            "",
            REPORT_END_MARKER,
        ]
    )
