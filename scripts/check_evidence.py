"""Validate committed offline evidence against a fresh deterministic run."""

from pathlib import Path

from secure_enterprise_ai_assistant.evaluation import validate_evidence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPOSITORY_ROOT / "reports" / "evaluation" / "latest.json"


def main() -> None:
    report = validate_evidence(REPORT_PATH)
    print(f"OK: {len(report['metrics'])} Messwerte stimmen mit dem eingecheckten Bericht überein")


if __name__ == "__main__":
    main()
