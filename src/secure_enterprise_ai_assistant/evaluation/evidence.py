"""Validation for the committed deterministic evaluation evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from secure_enterprise_ai_assistant.evaluation.runner import DEFAULT_SUITE, run_evaluation


class EvidenceValidationError(RuntimeError):
    """Raised when committed evidence differs from a fresh offline evaluation."""


def validate_evidence(
    report_path: Path,
    suite_path: Path = DEFAULT_SUITE,
) -> dict[str, Any]:
    """Recompute the suite and require exact content equality with committed evidence."""
    try:
        committed = json.loads(report_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceValidationError(f"Evidence report not found: {report_path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceValidationError("Evidence report is not valid JSON.") from exc

    measured = run_evaluation(suite_path)
    if committed != measured:
        differing_sections = sorted(
            key for key in set(committed) | set(measured) if committed.get(key) != measured.get(key)
        )
        raise EvidenceValidationError(
            "Committed evaluation evidence does not match a fresh offline run; "
            f"differing sections: {differing_sections}"
        )
    return measured
