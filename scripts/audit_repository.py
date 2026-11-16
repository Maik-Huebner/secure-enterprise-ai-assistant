"""Run the repository audit from any current working directory."""

from pathlib import Path

from secure_enterprise_ai_assistant.quality import audit_repository

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for result in audit_repository(REPOSITORY_ROOT):
        print(f"OK: {result}")


if __name__ == "__main__":
    main()
