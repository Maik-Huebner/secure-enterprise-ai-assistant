"""Local stdio MCP client used for the deterministic, verified full-assessment report."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from secure_enterprise_ai_assistant.core.labels import format_eur, format_pct, label
from secure_enterprise_ai_assistant.core.language import REPORT_END_MARKER
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.mcp.environment import server_environment
from secure_enterprise_ai_assistant.models.orchestration import RouteDecision

MCP_MODULE = "secure_enterprise_ai_assistant.mcp.server"
HARD_DECLINE_RULES = {"RULE-001", "RULE-006", "RULE-007"}

MCP_TOOL_NAMES = (
    "get_customer_case",
    "analyze_financial_case",
    "check_compliance",
    "search_internal_knowledge",
)


class MCPClientError(RuntimeError):
    """Raised when the local MCP server returns unusable structured output."""


def knowledge_query_for(failed_messages: list[str]) -> str:
    """Build the German policy-evidence query used for a full assessment."""
    base = (
        "Richtlinien zu Schuldendienstquote, Tragfähigkeit, Pflichtunterlagen, KYC, "
        "Risikoklasse und Entscheidungskontrollen"
    )
    return " ".join([base, *failed_messages])[:900]


class VerifiedMCPReportBuilder:
    """Build a complete report only from structured results fetched over MCP."""

    def __init__(self, timeout_seconds: int | None = None) -> None:
        self.timeout_seconds = timeout_seconds or get_settings().mcp_request_timeout_seconds

    def build(self, query: str, route: RouteDecision) -> str:
        """Fetch all evidence in one stdio session and render a bounded report."""
        del query  # The report depends only on the case; the free-text request is not reused.
        if route.case_id is None:
            raise MCPClientError("Eine vollständige Prüfung benötigt eine Fall-ID.")
        try:
            evidence = asyncio.run(self._fetch_with_timeout(route.case_id))
        except TimeoutError as exc:
            raise MCPClientError(
                "Die lokale MCP-Abfrage hat das Zeitlimit von "
                f"{self.timeout_seconds} Sekunden überschritten."
            ) from exc
        return self._render(route.case_id, evidence)

    async def _fetch_with_timeout(self, case_id: str) -> dict[str, dict[str, Any]]:
        return await asyncio.wait_for(self._fetch(case_id), timeout=self.timeout_seconds)

    async def _fetch(self, case_id: str) -> dict[str, dict[str, Any]]:
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", MCP_MODULE], env=server_environment()
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                calls = {
                    "case": await session.call_tool("get_customer_case", {"case_id": case_id}),
                    "financial": await session.call_tool(
                        "analyze_financial_case", {"case_id": case_id}
                    ),
                    "compliance": await session.call_tool("check_compliance", {"case_id": case_id}),
                }
                compliance_content = calls["compliance"].structuredContent or {}
                failed_messages = [
                    str(finding.get("message", ""))
                    for finding in compliance_content.get("findings", [])
                    if not finding.get("passed", False)
                ]
                calls["knowledge"] = await session.call_tool(
                    "search_internal_knowledge",
                    {"question": knowledge_query_for(failed_messages), "top_k": 5},
                )
        structured: dict[str, dict[str, Any]] = {}
        for name, result in calls.items():
            if result.isError or not isinstance(result.structuredContent, dict):
                raise MCPClientError(
                    f"Das MCP-Werkzeug lieferte keine strukturierten Daten: {name}."
                )
            structured[name] = result.structuredContent
        return structured

    @staticmethod
    def _render(case_id: str, evidence: dict[str, dict[str, Any]]) -> str:
        case = evidence["case"]["case"]
        customer = case["customer"]
        application = case["application"]
        metrics = evidence["financial"]["metrics"]
        findings = evidence["compliance"]["findings"]
        failed = [finding for finding in findings if not finding["passed"]]
        failed_ids = {finding["rule_id"] for finding in failed}
        if failed_ids & HARD_DECLINE_RULES:
            recommendation = "Ablehnung"
            rationale = "Mindestens ein nicht behebbares hartes Ablehnungskriterium ist verletzt."
        elif failed:
            recommendation = "Manuelle Prüfung"
            rationale = "Mindestens eine Warnung oder behebbare Nachweislücke ist offen."
        else:
            recommendation = "Genehmigungskandidat"
            rationale = "Alle maschinenlesbaren Prüfregeln wurden bestanden."

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
                f"**Empfehlung: {recommendation}.** {rationale}",
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
                *[f"- `{name}`" for name in MCP_TOOL_NAMES],
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
