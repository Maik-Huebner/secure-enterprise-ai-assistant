"""Scoring helpers for the answer-quality evaluation (deterministic parts)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

DOCUMENT_ID = re.compile(r"\bNB-[A-Z]{3}-\d{3}\b")
NO_ANSWER_MARKERS = (
    "keine ausreichend passende richtlinie",
    "keine passende",
    "nicht beantworten",
    "keine informationen",
    "enthält dazu keine",
    "nicht in den nachweisen",
    "nicht enthalten",
)


def fact_hits(answer: str, facts: Sequence[Sequence[str]]) -> list[bool]:
    """For each expected fact: is any accepted spelling contained (case-insensitive)?"""
    lowered = answer.casefold()
    return [any(option.casefold() in lowered for option in options) for options in facts]


def declined(answer: str) -> bool:
    lowered = answer.casefold()
    return any(marker in lowered for marker in NO_ANSWER_MARKERS)


def citation_check(answer: str, grounded: set[str], expected: Sequence[str]) -> dict[str, Any]:
    """Cited IDs must be grounded (retrieved or referenced in the evidence); one expected cited."""
    cited = set(DOCUMENT_ID.findall(answer))
    return {
        "cited": sorted(cited),
        "only_grounded_cited": cited <= grounded,
        "expected_cited": bool(cited & set(expected)) if expected else None,
    }


def ratio(values: Sequence[bool | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return round(sum(usable) / len(usable), 4) if usable else None
