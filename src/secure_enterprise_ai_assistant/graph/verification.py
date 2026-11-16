"""Deterministic checks of a model answer against the evidence it was given.

They catch the failure modes seen in practice: invented numbers, citations of documents that
were not retrieved, missing citations, and English labels in German answers. They cannot prove
that every sentence is supported; that is what the faithfulness judge in the answer-quality
evaluation estimates.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from secure_enterprise_ai_assistant.core.language import forbidden_labels_in
from secure_enterprise_ai_assistant.graph.evidence_text import (
    Evidence,
    evidence_document_ids,
    passages,
    prompt_context,
)

DOCUMENT_ID = re.compile(r"\bNB-[A-Z]{3}-\d{3}\b")
# Anything that looks like a document reference but is not a real ID ("NB-DOC-XXX").
ID_LIKE = re.compile(r"\bNB-[A-Za-z]{2,4}-[A-Za-z0-9?*.]{1,4}\b")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Small integers are list markers, counts or section numbers far more often than facts.
IGNORED_BELOW = Decimal(13)


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text).normalize()
    except InvalidOperation:
        return None


def interpretations(token: str) -> set[Decimal]:
    """Every plausible reading of a number token ('18.250' may be 18250 or 18.25)."""
    candidates: set[str] = set()
    if "," in token and "." in token:
        candidates.add(token.replace(".", "").replace(",", "."))  # German 1.234,56
        candidates.add(token.replace(",", ""))  # English 1,234.56
    elif "," in token:
        candidates.add(token.replace(",", "."))
        candidates.add(token.replace(",", ""))
    elif "." in token:
        candidates.add(token)
        candidates.add(token.replace(".", ""))
    else:
        candidates.add(token)
    return {value for value in map(_decimal, candidates) if value is not None}


def numbers_in(text: str) -> set[Decimal]:
    """All readings of all numbers in a text."""
    return {value for token in NUMBER.findall(text) for value in interpretations(token)}


def unsupported_numbers(answer: str, allowed: set[Decimal]) -> list[str]:
    """Number tokens of the answer for which no reading occurs in ``allowed``."""
    tokens = []
    for token in NUMBER.findall(answer):
        readings = interpretations(token)
        if not readings or max(readings) < IGNORED_BELOW:
            continue
        if not readings & allowed:
            tokens.append(token)
    return sorted(set(tokens))


def verify_answer(answer: str, evidence: Evidence, case_id: str | None = None) -> list[str]:
    """Return a list of German issue descriptions; empty means the answer passed."""
    issues: list[str] = []
    allowed_numbers = numbers_in(prompt_context(evidence))  # includes all cited sections
    if case_id:
        allowed_numbers |= numbers_in(case_id)
    unsupported = unsupported_numbers(answer, allowed_numbers)
    if unsupported:
        issues.append(
            "Diese Zahlen stehen nicht in den Nachweisen: " + ", ".join(unsupported[:5]) + "."
        )
    cited = set(DOCUMENT_ID.findall(answer))
    context = prompt_context(evidence)
    # Retrieved documents, plus documents the evidence itself refers to ("siehe NB-ESC-001").
    grounded = evidence_document_ids(evidence) | set(DOCUMENT_ID.findall(context))
    unknown = sorted(cited - grounded)
    if unknown:
        issues.append(
            "Diese Dokumente wurden nicht gefunden und dürfen nicht zitiert werden: "
            + ", ".join(unknown)
            + "."
        )
    placeholders = sorted(
        token for token in set(ID_LIKE.findall(answer)) if not DOCUMENT_ID.fullmatch(token)
    )
    if placeholders:
        issues.append(
            "Erfinde keine Dokumentkennungen oder Platzhalter: " + ", ".join(placeholders) + "."
        )
    if passages(evidence) and not cited:
        issues.append("Nenne für Aussagen zu Richtlinien die Dokument-ID und den Abschnitt.")
    english = forbidden_labels_in(answer)
    if english:
        issues.append(
            "Verwende deutsche statt englischer Bezeichnungen: " + ", ".join(english) + "."
        )
    if len(answer.strip()) < 20:
        issues.append("Die Antwort ist leer oder zu kurz.")
    return issues
