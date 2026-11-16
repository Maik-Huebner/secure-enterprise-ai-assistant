"""Reject explicit capability-escalation and prompt-exfiltration attempts."""

from __future__ import annotations

import re

from secure_enterprise_ai_assistant.core.logs import get_logger

logger = get_logger(__name__)


class UnsafeInputError(ValueError):
    """Raised for input that attempts to cross the assistant trust boundary."""


BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions?", re.I),
    ),
    (
        "prompt_exfiltration",
        re.compile(r"(reveal|show|print|leak)\s+(the\s+)?(system|developer)\s+prompt", re.I),
    ),
    (
        "shell_execution",
        re.compile(r"(execute|run)\s+(an?\s+)?(shell|terminal)\s+command", re.I),
    ),
)


def validate_user_query(query: str) -> str:
    """Validate length, control characters, and explicit trust-boundary attacks."""
    normalized = " ".join(query.split())
    if not 3 <= len(normalized) <= 2000:
        raise UnsafeInputError("Query must contain between 3 and 2000 characters.")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in query):
        raise UnsafeInputError("Query contains unsupported control characters.")
    for category, pattern in BLOCKED_PATTERNS:
        if pattern.search(normalized):
            logger.warning(
                "input_blocked",
                extra={"category": category, "query_length": len(normalized)},
            )
            raise UnsafeInputError(f"Query blocked by security policy: {category}.")
    return normalized


def scan_untrusted_content(content: str) -> list[str]:
    """Return security categories found in untrusted retrieved document content."""
    return [category for category, pattern in BLOCKED_PATTERNS if pattern.search(content)]
