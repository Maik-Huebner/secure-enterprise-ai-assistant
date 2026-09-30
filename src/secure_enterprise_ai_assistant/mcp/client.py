"""Local stdio MCP client used for deterministic evidence-verification fallback."""

from __future__ import annotations

import asyncio
import re
import sys
from decimal import Decimal
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.models.orchestration import RouteDecision

MCP_MODULE = "secure_enterprise_ai_assistant.mcp.server"
HARD_DECLINE_RULES = {"RULE-001", "RULE-006", "RULE-007"}

_GERMAN_FINDING_TEXT = {
    "KYC must not be rejected": "KYC darf nicht abgelehnt sein",
    "KYC must be verified before approval": "KYC muss vor Genehmigung verifiziert sein",
    "Required application documents must be present": (
        "Erforderliche Antragsunterlagen müssen vorliegen"
    ),
    "Submitted documents must be valid": "Eingereichte Dokumente müssen gültig sein",
    "Post-loan DTI review threshold": "Prüfschwelle für DTI nach Kredit",
    "Post-loan DTI hard limit": "Harte Obergrenze für DTI nach Kredit",
    "Risk class must remain inside credit appetite": (
        "Risikoklasse muss innerhalb der Kreditrisikovorgaben liegen"
    ),
    "Temporary employment stability": "Stabilität bei befristeter Beschäftigung",
    "Consumer-credit amount limit": "Betragsgrenze für Konsumentenkredite",
    "Standard term limit": "Standard-Laufzeitgrenze",
    "KYC status is": "KYC-Status ist",
    "required status is": "erforderlicher Status ist",
    "All mandatory documents are present": "Alle Pflichtdokumente liegen vor",
    "Missing or unusable mandatory documents": "Fehlende oder unbrauchbare Pflichtdokumente",
    "No expired or invalid documents found": (
        "Keine abgelaufenen oder ungültigen Dokumente gefunden"
    ),
    "Expired or invalid documents": "Abgelaufene oder ungültige Dokumente",
    "Post-loan DTI is": "DTI nach Kredit beträgt",
    "Risk class is": "Risikoklasse ist",
    "eligible classes are": "zulässige Klassen sind",
    "Employment is not temporary; rule is not applicable": (
        "Die Beschäftigung ist nicht befristet; die Regel ist nicht anwendbar"
    ),
    "Temporary employment continuity is": "Dauer der befristeten Beschäftigung beträgt",
    "Requested amount is": "Beantragter Betrag ist",
    "Requested term is": "Beantragte Laufzeit beträgt",
    "verified": "verifiziert",
    "pending": "ausstehend",
    "incomplete": "unvollständig",
    "rejected": "abgelehnt",
    "months": "Monate",
    "Maximum": "Höchstwert",
    "maximum": "Höchstwert",
}

_GERMAN_DISPLAY_VALUES = {
    "permanent": "unbefristet beschäftigt",
    "temporary": "befristet beschäftigt",
    "self_employed": "selbstständig",
    "retired": "im Ruhestand",
    "student": "in Ausbildung",
    "unemployed": "arbeitslos",
    "verified": "verifiziert",
    "pending": "ausstehend",
    "incomplete": "unvollständig",
    "rejected": "abgelehnt",
    "info": "Information",
    "warning": "Warnung",
    "critical": "kritisch",
}


class MCPClientError(RuntimeError):
    """Raised when the local MCP server returns unusable structured output."""


def _german_finding_message(message: str) -> str:
    """Translate fixed compliance presentation text without changing MCP evidence."""
    translated = message
    for source, target in _GERMAN_FINDING_TEXT.items():
        translated = translated.replace(source, target)
    translated = re.sub(
        r"EUR\s+(\d+(?:\.\d+)?)",
        lambda match: f"{_format_decimal_de(match.group(1))} EUR",
        translated,
    )
    translated = re.sub(
        r"\b(\d+\.\d+)(?=%)",
        lambda match: match.group(1).replace(".", ","),
        translated,
    )
    return translated


def _german_display(value: str) -> str:
    """Return the German display label for a structured enum value."""
    return _GERMAN_DISPLAY_VALUES.get(value, value)


def _format_decimal_de(value: Any, places: int = 2) -> str:
    """Format one structured numeric value for the German presentation layer."""
    formatted = f"{Decimal(str(value)):,.{places}f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


class VerifiedMCPReportBuilder:
    """Build a complete report only from structured results fetched over MCP."""

    def __init__(self, timeout_seconds: int | None = None) -> None:
        self.timeout_seconds = timeout_seconds or get_settings().mcp_request_timeout_seconds

    def build(self, query: str, route: RouteDecision) -> str:
        """Fetch all evidence in one stdio session and render a bounded report."""
        if route.case_id is None:
            raise MCPClientError("A full assessment requires a case ID.")
        try:
            evidence = asyncio.run(self._fetch_with_timeout(query, route.case_id))
        except TimeoutError as exc:
            raise MCPClientError(
                f"Local MCP evidence collection exceeded {self.timeout_seconds} seconds."
            ) from exc
        return self._render(route.case_id, evidence)

    async def _fetch_with_timeout(self, query: str, case_id: str) -> dict[str, dict[str, Any]]:
        return await asyncio.wait_for(
            self._fetch(query, case_id),
            timeout=self.timeout_seconds,
        )

    async def _fetch(self, query: str, case_id: str) -> dict[str, dict[str, Any]]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", MCP_MODULE],
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
            recommendation = "DECLINE (Ablehnung)"
            rationale = "Mindestens ein nicht behebbares hartes Ablehnungskriterium ist verletzt."
        elif failed:
            recommendation = "MANUAL REVIEW (manuelle Prüfung)"
            rationale = "Mindestens eine Warnung oder behebbare Evidenzlücke ist offen."
        else:
            recommendation = "APPROVE CANDIDATE (Genehmigungskandidat)"
            rationale = "Alle maschinenlesbaren Prüfregeln wurden bestanden."

        finding_lines = [
            (
                f"- **{item['rule_id']}** "
                f"({_german_display(item['severity'])}): "
                f"{'PASS (bestanden)' if item['passed'] else 'FAIL (nicht bestanden)'} — "
                f"{_german_finding_message(item['message'])}"
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
                "## Empfehlung",
                f"**Empfehlung: {recommendation}.** {rationale}",
                "Diese Ausgabe ist Entscheidungshilfe; die finale Entscheidung bleibt beim "
                "autorisierten menschlichen Prüfer.",
                "",
                "## Validierte Falldaten",
                f"- Synthetischer Kunde: {customer['full_name']} ({customer['customer_id']})",
                "- Beschäftigung: "
                f"{_german_display(customer['employment_status'])}, "
                f"{customer['months_employed']} Monate",
                f"- KYC: {_german_display(customer['kyc_status'])}; "
                f"Risikoklasse: {customer['risk_class']}",
                f"- Antrag: {_format_decimal_de(application['requested_amount_eur'])} EUR über "
                f"{application['term_months']} Monate zu "
                f"{_format_decimal_de(application['annual_interest_rate_pct'])} % p.a.",
                "",
                "## Deterministische finanzielle Kennzahlen",
                f"- Monatliche Rate: **{_format_decimal_de(metrics['monthly_payment_eur'])} EUR**",
                "- DTI vor Kredit: "
                f"**{_format_decimal_de(metrics['debt_to_income_before_pct'])} %**",
                "- DTI nach Kredit: "
                f"**{_format_decimal_de(metrics['debt_to_income_after_pct'])} %**",
                f"- Gesamtzins: **{_format_decimal_de(metrics['total_interest_eur'])} EUR**",
                "- Gesamtrückzahlung: "
                f"**{_format_decimal_de(metrics['total_repayment_eur'])} EUR**",
                "Die Zahlen stammen unverändert aus `analyze_financial_case`; es wurde keine "
                "LLM-Arithmetik verwendet.",
                "",
                "## Compliance- und Regelwerksprüfung",
                *finding_lines,
                "",
                "## Verifizierte Quellen",
                *source_lines,
                "",
                "## Verwendete MCP-Werkzeuge",
                "- `get_customer_case`",
                "- `analyze_financial_case`",
                "- `check_compliance`",
                "- `search_internal_knowledge`",
                "Alle Evidenzen wurden in einer echten lokalen MCP-stdio-Session abgerufen.",
                "",
                "## Prüferhinweise",
                "Offene Warnungen sind vor einer Genehmigung nachvollziehbar zu disponieren. "
                "Kritische harte Ablehnungsregeln dürfen nicht durch Sprachmodelltext "
                "überschrieben "
                "werden. Referenzlabels sind nicht Teil dieser Evidenz und wurden nicht an "
                "das Modell oder den Berichtsgenerator übergeben.",
                "",
                "END OF VERIFIED REPORT",
            ]
        )
