"""Measured, reproducible evaluation suite."""

from pathlib import Path
from typing import Any


def run_evaluation(suite_path: Path | None = None) -> dict[str, Any]:
    """Lazily import the runner so ``python -m`` remains warning-free."""
    from secure_enterprise_ai_assistant.evaluation.runner import DEFAULT_SUITE
    from secure_enterprise_ai_assistant.evaluation.runner import (
        run_evaluation as _run_evaluation,
    )

    return _run_evaluation(suite_path or DEFAULT_SUITE)


def validate_evidence(report_path: Path, suite_path: Path | None = None) -> dict[str, Any]:
    """Validate committed evidence without importing the evaluator eagerly."""
    from secure_enterprise_ai_assistant.evaluation.evidence import (
        validate_evidence as _validate_evidence,
    )
    from secure_enterprise_ai_assistant.evaluation.runner import DEFAULT_SUITE

    return _validate_evidence(report_path, suite_path or DEFAULT_SUITE)


__all__ = ["run_evaluation", "validate_evidence"]
