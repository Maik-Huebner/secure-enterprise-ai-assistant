"""Central German display labels and number formatting.

Domain data keeps stable technical codes (for example ``rejected``). These helpers only render
them for people, so every layer shows the same German wording.
"""

from __future__ import annotations

from decimal import Decimal

CODE_LABELS: dict[str, str] = {
    # Employment status
    "permanent": "unbefristet beschäftigt",
    "temporary": "befristet beschäftigt",
    "self_employed": "selbstständig",
    "retired": "im Ruhestand",
    "student": "in Ausbildung",
    "unemployed": "arbeitslos",
    # KYC and application status
    "verified": "verifiziert",
    "pending": "ausstehend",
    "incomplete": "unvollständig",
    "rejected": "abgelehnt",
    "draft": "Entwurf",
    "submitted": "eingereicht",
    "under_review": "in Prüfung",
    "approved": "genehmigt",
    "manual_review": "manuelle Prüfung",
    # Document status and types
    "present": "vorhanden",
    "missing": "fehlend",
    "expired": "abgelaufen",
    "invalid": "ungültig",
    "identity_document": "Ausweisdokument",
    "income_statement": "Einkommensnachweis",
    "bank_statements_90_days": "Kontoauszüge der letzten 90 Tage",
    "credit_application_form": "Kreditantragsformular",
    # Compliance severity
    "info": "Information",
    "warning": "Warnung",
    "critical": "kritisch",
    # Decision recommendations
    "approve": "Genehmigungskandidat",
    "decline": "Ablehnung",
}


def label(code: str) -> str:
    """Return the German label for a technical code, or the code itself."""
    return CODE_LABELS.get(code, code)


def format_decimal(value: Decimal | float | int | str, places: int = 2) -> str:
    """Format a number in German notation, e.g. 18250.5 -> '18.250,50'."""
    formatted = f"{Decimal(str(value)):,.{places}f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_eur(value: Decimal | float | int | str) -> str:
    """Format an amount as German euro text, e.g. '18.250,00 EUR'."""
    return f"{format_decimal(value)} EUR"


def format_pct(value: Decimal | float | int | str, places: int = 2) -> str:
    """Format a percentage in German notation, e.g. '44,95 %'."""
    return f"{format_decimal(value, places)} %"
