"""Local stdio MCP client used for deterministic evidence-verification fallback."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from secure_enterprise_ai_assistant.models.orchestration import RouteDecision

MCP_MODULE = "secure_enterprise_ai_assistant.mcp.server"
HARD_DECLINE_RULES = {"RULE-001", "RULE-006", "RULE-007"}


class MCPClientError(RuntimeError):
    """Raised when the local MCP server returns unusable structured output."""


class VerifiedMCPReportBuilder:
    """Build a complete report only from structured results fetched over MCP."""

    def build(self, query: str, route: RouteDecision) -> str:
        """Fetch all evidence in one stdio session and render a bounded report."""
        if route.case_id is None:
            raise MCPClientError("A full assessment requires a case ID.")
        evidence = asyncio.run(self._fetch(query, route.case_id))
        return self._render(route.case_id, evidence)

    async def _fetch(self, query: str, case_id: str) -> dict[str, dict[str, Any]]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", MCP_MODULE],
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                calls = {
                    "case": await session.call_tool(
                        "get_customer_case", {"case_id": case_id}
                    ),
                    "financial": await session.call_tool(
                        "analyze_financial_case", {"case_id": case_id}
                    ),
                    "compliance": await session.call_tool(
                        "check_compliance", {"case_id": case_id}
                    ),
                }
                compliance_content = calls["compliance"].structuredContent or {}
                failed_messages = " ".join(
                    finding.get("message", "")
                    for finding in compliance_content.get("findings", [])
                    if not finding.get("passed", False)
                )
                calls["knowledge"] = await session.call_tool(
                    "search_internal_knowledge",
                    {
                        "question": (
                            f"Policy evidence for {query} {failed_messages} DTI affordability "
                            "mandatory documents KYC risk classification decision controls"
                        ),
                        "top_k": 5,
                    },
                )
        structured: dict[str, dict[str, Any]] = {}
        for name, result in calls.items():
            if result.isError or not isinstance(result.structuredContent, dict):
                raise MCPClientError(f"MCP tool returned no structured {name} evidence.")
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
            recommendation = "DECLINE"
            rationale = "Mindestens ein nicht behebbarer Hard-Decline-Indikator ist verletzt."
        elif failed:
            recommendation = "MANUAL REVIEW"
            rationale = "Mindestens eine Warnung oder behebbare Evidenzlücke ist offen."
        else:
            recommendation = "APPROVE CANDIDATE"
            rationale = "Alle maschinenlesbaren Prüfregeln wurden bestanden."

        finding_lines = [
            (
                f"- **{item['rule_id']}** ({item['severity']}): "
                f"{'PASS' if item['passed'] else 'FAIL'} — {item['message']}"
            )
            for item in findings
        ]
        source_map: dict[str, tuple[str, str, str]] = {}
        for result in evidence["knowledge"].get("results", []):
            chunk = result["chunk"]
            source_map[chunk["document_id"]] = (
                chunk["title"],
                chunk["section"],
                chunk["version"],
            )
        source_lines = [
            f"- **{document_id}** v{version} — {title}, Abschnitt {section}"
            for document_id, (title, section, version) in sorted(source_map.items())
        ]
        if not source_lines:
            source_lines = ["- Keine ausreichend relevante Policy-Quelle gefunden."]

        return "\n".join(
            [
                f"# Entscheidungsvorlage — {case_id}",
                "",
                "## Executive Recommendation",
                f"**Empfehlung: {recommendation}.** {rationale}",
                "Diese Ausgabe ist Entscheidungshilfe; die finale Entscheidung bleibt beim "
                "autorisierten menschlichen Reviewer.",
                "",
                "## Validierte Falldaten",
                f"- Synthetischer Kunde: {customer['full_name']} ({customer['customer_id']})",
                f"- Beschäftigung: {customer['employment_status']}, "
                f"{customer['months_employed']} Monate",
                f"- KYC: {customer['kyc_status']}; Risk Class: {customer['risk_class']}",
                f"- Antrag: EUR {application['requested_amount_eur']} über "
                f"{application['term_months']} Monate zu "
                f"{application['annual_interest_rate_pct']}% p.a.",
                "",
                "## Deterministische finanzielle Kennzahlen",
                f"- Monatliche Rate / monthly payment: **EUR {metrics['monthly_payment_eur']}**",
                f"- DTI vor Kredit: **{metrics['debt_to_income_before_pct']}%**",
                f"- DTI nach Kredit: **{metrics['debt_to_income_after_pct']}%**",
                f"- Gesamtzins: **EUR {metrics['total_interest_eur']}**",
                f"- Gesamtrückzahlung: **EUR {metrics['total_repayment_eur']}**",
                "Die Zahlen stammen unverändert aus `analyze_financial_case`; es wurde keine "
                "LLM-Arithmetik verwendet.",
                "",
                "## Compliance- und Policy-Prüfung",
                *finding_lines,
                "",
                "## Verifizierte Quellen",
                *source_lines,
                "",
                "## Reviewer-Hinweise",
                "Offene Warnungen sind vor einer Genehmigung nachvollziehbar zu disponieren. "
                "Kritische Hard-Decline-Regeln dürfen nicht durch Sprachmodelltext überschrieben "
                "werden. Ground-Truth-Labels sind nicht Teil dieser Evidenz und wurden nicht an "
                "das Modell oder den Report-Builder übergeben.",
                "",
                "END OF VERIFIED REPORT",
            ]
        )
