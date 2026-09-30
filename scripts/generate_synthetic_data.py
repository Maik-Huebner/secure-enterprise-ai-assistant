"""Regenerate the synthetic case resources and evaluation-only labels."""

import argparse
from pathlib import Path

from secure_enterprise_ai_assistant.development.synthetic_data import write_dataset

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = (
    REPOSITORY_ROOT
    / "src"
    / "secure_enterprise_ai_assistant"
    / "resources"
    / "customers"
    / "credit_cases.json"
)
LABELS_PATH = REPOSITORY_ROOT / "data" / "demo" / "case_ground_truth.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-count", type=int, default=48)
    args = parser.parse_args()
    write_dataset(CASES_PATH, LABELS_PATH, case_count=args.case_count)


if __name__ == "__main__":
    main()
