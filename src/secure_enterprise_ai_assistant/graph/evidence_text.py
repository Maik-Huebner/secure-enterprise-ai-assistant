"""Turn structured MCP evidence into prompt context and into deterministic German answers."""

from __future__ import annotations

from typing import Any

from secure_enterprise_ai_assistant.core.labels import format_decimal, format_eur, format_pct, label
from secure_enterprise_ai_assistant.mcp.client import RECOMMENDATION_LABELS

Evidence = dict[str, dict[str, Any]]
EXCERPT_CHARS = 600


def passages(evidence: Evidence) -> list[dict[str, Any]]:
    """Retrieved policy chunks, empty if the search found nothing relevant."""
    knowledge = evidence.get("knowledge") or {}
    if knowledge.get("out_of_scope"):
        return []
    return [result["chunk"] for result in knowledge.get("results", [])]


def evidence_document_ids(evidence: Evidence) -> set[str]:
    return {chunk["document_id"] for chunk in passages(evidence)}


def case_lines(evidence: Evidence) -> list[str]:
    case = evidence["case"]["case"]
    customer, application = case["customer"], case["application"]
    documents = ", ".join(
        f"{label(item['document_type'])}: {label(item['status'])}" for item in case["documents"]
    )
    return [
        f"Fall-ID: {case['case_id']}",
        f"Synthetischer Kunde: {customer['full_name']} ({customer['customer_id']}), "
        f"{customer['age']} Jahre",
        f"Beschäftigung: {label(customer['employment_status'])}, "
        f"{customer['months_employed']} Monate",
        f"Monatliches Nettoeinkommen: {format_eur(customer['monthly_net_income_eur'])}",
        "Bestehende monatliche Verpflichtungen: "
        f"{format_eur(customer['existing_monthly_debt_eur'])}",
        f"KYC-Status: {label(customer['kyc_status'])}; Risikoklasse: {customer['risk_class']}",
        f"Antrag: {format_eur(application['requested_amount_eur'])} über "
        f"{application['term_months']} Monate zu "
        f"{format_pct(application['annual_interest_rate_pct'])} p. a., "
        f"Zweck: {application['purpose']}",
        f"Unterlagen: {documents}",
    ]


def financial_lines(evidence: Evidence) -> list[str]:
    metrics = evidence["financial"]["metrics"]
    return [
        f"Monatliche Rate: {format_eur(metrics['monthly_payment_eur'])}",
        f"DTI vor Kredit: {format_pct(metrics['debt_to_income_before_pct'])}",
        f"DTI nach Kredit: {format_pct(metrics['debt_to_income_after_pct'])}",
        f"Gesamtzins: {format_eur(metrics['total_interest_eur'])}",
        f"Gesamtrückzahlung: {format_eur(metrics['total_repayment_eur'])}",
        "Monatliche Verpflichtungen nach Kredit (bestehende + neue Rate): "
        f"{format_eur(metrics['monthly_obligations_after_eur'])}",
        "Anstieg der DTI: "
        f"{format_decimal(metrics['debt_to_income_change_pct_points'])} Prozentpunkte",
    ]


def compliance_lines(evidence: Evidence) -> list[str]:
    compliance = evidence["compliance"]
    lines = [
        f"{item['rule_id']} ({label(item['severity'])}): "
        f"{'bestanden' if item['passed'] else 'nicht bestanden'} – {item['message']}"
        for item in compliance["findings"]
    ]
    decision = compliance["decision"]
    lines.append(
        f"Regelbasierte Empfehlung: {RECOMMENDATION_LABELS[decision['recommendation']]} – "
        f"{decision['rationale']}"
    )
    return lines


def prompt_context(evidence: Evidence) -> str:
    """Evidence block for the model. Document text is fenced as data, never as instructions."""
    blocks: list[str] = []
    if "case" in evidence:
        blocks.append(
            '<falldaten quelle="get_customer_case">\n'
            + "\n".join(case_lines(evidence))
            + "\n</falldaten>"
        )
    if "financial" in evidence:
        blocks.append(
            '<kennzahlen quelle="analyze_financial_case">\n'
            + "\n".join(financial_lines(evidence))
            + "\n</kennzahlen>"
        )
    if "compliance" in evidence:
        blocks.append(
            '<pruefergebnisse quelle="check_compliance">\n'
            + "\n".join(compliance_lines(evidence))
            + "\n</pruefergebnisse>"
        )
    for chunk in passages(evidence):
        blocks.append(
            f'<richtlinie id="{chunk["document_id"]}" abschnitt="{chunk["section"]}" '
            f'titel="{chunk["title"]}" version="{chunk["version"]}">\n'
            f"{chunk['content'][:EXCERPT_CHARS]}\n</richtlinie>"
        )
    return "\n\n".join(blocks) if blocks else "<keine_nachweise/>"


def deterministic_answer(intent: str, evidence: Evidence) -> str:
    """Verified fallback: an answer built only from structured evidence, without a model."""
    sections: list[str] = []
    if "case" in evidence and intent in {"customer_case", "financial_analysis", "compliance_check"}:
        sections.append(
            "## Geprüfte Falldaten\n" + "\n".join(f"- {line}" for line in case_lines(evidence))
        )
    if "financial" in evidence:
        sections.append(
            "## Finanzielle Kennzahlen (analyze_financial_case)\n"
            + "\n".join(f"- {line}" for line in financial_lines(evidence))
        )
    if "compliance" in evidence:
        sections.append(
            "## Prüfergebnisse (check_compliance)\n"
            + "\n".join(f"- {line}" for line in compliance_lines(evidence))
        )
    chunks = passages(evidence)
    if chunks:
        sections.append(
            "## Textstellen aus den Richtlinien\n"
            + "\n".join(
                f"- **{chunk['document_id']}, Abschnitt {chunk['section']}**: "
                f"{' '.join(chunk['content'].split())[:EXCERPT_CHARS]}"
                for chunk in chunks[:3]
            )
        )
    elif intent == "knowledge":
        sections.append(NO_ANSWER)
    return "\n\n".join(sections)


NO_ANSWER = (
    "Dazu enthält die Wissensbasis keine ausreichend passende Richtlinie. "
    "Bitte formuliere die Frage genauer oder wende dich an die zuständige Fachabteilung."
)
