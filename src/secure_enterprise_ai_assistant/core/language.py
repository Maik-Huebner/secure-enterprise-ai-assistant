"""Central language rules for user-facing NovaBank responses (German throughout)."""

from __future__ import annotations

GERMAN_RESPONSE_RULE = (
    "Antworte vollständig auf Deutsch. Überschriften, Tabellenbezeichnungen, Erklärungen, "
    "Empfehlungen und Fehlermeldungen sind deutsch. Technische Kennungen bleiben "
    "unverändert: CASE-IDs, RULE-IDs, NovaBank-Dokument-IDs, Modellnamen, MCP und DTI."
)

REPORT_END_MARKER = "ENDE DES GEPRÜFTEN BERICHTS"

# English presentation labels that small local models tend to emit despite German prompts.
FORBIDDEN_ENGLISH_LABELS = (
    "Case Metrics",
    "Evidence Source",
    "Monthly Payment",
    "Total Interest",
    "Total Repayment",
    "Language-Model Interpretation",
    "Recommendation",
    "Decision Brief",
    "Findings",
)


def forbidden_labels_in(response: str) -> list[str]:
    """List English presentation labels that must not appear in a German response."""
    normalized = response.casefold()
    return [label for label in FORBIDDEN_ENGLISH_LABELS if label.casefold() in normalized]
