"""Central language rules for user-facing NovaBank responses."""

from __future__ import annotations

import re

GERMAN_RESPONSE_RULE = (
    "Respond completely in the language of the user's request. For German requests, write all "
    "headings, table labels, explanations, recommendations, and user-visible error messages in "
    "German. Keep technical identifiers and established technical names such as CASE IDs, RULE "
    "IDs, NovaBank document IDs, model names, MCP, DTI, and CrewAI unchanged. Quoted original "
    "document titles may remain in their source language."
)

FORBIDDEN_ENGLISH_GERMAN_LABELS = (
    "NovaBank Case Metrics",
    "Evidence Source",
    "Monthly Payment",
    "Language-Model Interpretation",
)

_GERMAN_MARKERS = re.compile(
    r"\b(?:bitte|berechne|belastung|deutsch|erstelle|fuer|für|kredit|"
    r"moechte|möchte|pruefe|prüfe|unterlagen|vollstaendig|vollständig|"
    r"welche|welcher|welches|zeige)\b",
    re.IGNORECASE,
)


def is_german_request(query: str) -> bool:
    """Detect the explicit German phrasing used by supported assistant requests."""
    return bool(_GERMAN_MARKERS.search(query))


def response_language_instruction(query: str) -> str:
    """Return a mandatory output-language instruction for one user request."""
    if is_german_request(query):
        return (
            "Ausgabesprache für diese Anfrage: Deutsch. Formuliere die vollständige "
            "benutzerseitige Antwort auf Deutsch. Das gilt insbesondere für Überschriften, "
            "Tabellenbezeichnungen, Erläuterungen und Empfehlungen. Verwende deutsche statt "
            "englischer Antwortüberschriften. Technische IDs und etablierte technische Bezeichner "
            "sowie zitierte Originaltitel von Dokumenten bleiben unverändert."
        )
    return GERMAN_RESPONSE_RULE


def forbidden_labels_for_response(query: str, response: str) -> list[str]:
    """List English presentation labels forbidden in a German response."""
    if not is_german_request(query):
        return []
    normalized = response.casefold()
    return [label for label in FORBIDDEN_ENGLISH_GERMAN_LABELS if label.casefold() in normalized]
