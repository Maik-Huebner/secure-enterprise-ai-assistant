"""Regenerate the synthetic case resources and evaluation-only labels."""

from pathlib import Path

from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser
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
    parser = GermanArgumentParser(
        description="Synthetische Kreditfälle und Bewertungsetiketten neu erzeugen."
    )
    parser.add_argument(
        "--anzahl",
        "--case-count",
        dest="case_count",
        type=int,
        default=48,
        metavar="N",
        help="Anzahl der Fälle (mindestens 40)",
    )
    args = parser.parse_args()
    write_dataset(CASES_PATH, LABELS_PATH, case_count=args.case_count)


if __name__ == "__main__":
    main()
