"""Stable locations for read-only data shipped inside the installed package."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = PACKAGE_ROOT / "resources"
CASES_PATH = RESOURCE_ROOT / "customers" / "credit_cases.json"
RULES_PATH = RESOURCE_ROOT / "compliance" / "rules.json"
KNOWLEDGE_ROOT = RESOURCE_ROOT / "knowledge_base"
EVALUATION_SUITE_PATH = RESOURCE_ROOT / "evaluation" / "evaluation_suite.json"
GUARDRAIL_SUITE_PATH = RESOURCE_ROOT / "evaluation" / "guardrail_suite.json"
RETRIEVAL_SUITE_PATH = RESOURCE_ROOT / "evaluation" / "retrieval_suite.json"
ROUTING_SUITE_PATH = RESOURCE_ROOT / "evaluation" / "routing_suite.json"
RETRIEVAL_THRESHOLDS_PATH = RESOURCE_ROOT / "retrieval" / "thresholds.json"
INTENT_EXAMPLES_PATH = RESOURCE_ROOT / "routing" / "intent_examples.json"
CASE_ASSIGNMENTS_PATH = RESOURCE_ROOT / "security" / "case_assignments.json"


def require_resource(path: Path, description: str) -> Path:
    """Return a packaged resource or raise an actionable installation error."""
    if not path.exists():
        raise FileNotFoundError(
            f"Erforderliche Ressource fehlt in der Installation ({description}): {path.name}"
        )
    return path
