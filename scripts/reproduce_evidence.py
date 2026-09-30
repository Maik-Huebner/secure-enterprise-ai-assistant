"""Regenerate deterministic offline evaluation evidence for this repository."""

from pathlib import Path

from secure_enterprise_ai_assistant.evaluation.runner import run_evaluation, write_report

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPOSITORY_ROOT / "reports" / "evaluation" / "latest.json"


def main() -> None:
    report = run_evaluation()
    write_report(report, REPORT_PATH)
    print(f"Wrote deterministic evidence: {REPORT_PATH}")


if __name__ == "__main__":
    main()
