"""Regenerate the synthetic policy resources shipped with the package."""

from pathlib import Path

from secure_enterprise_ai_assistant.development.knowledge_base import write_knowledge_base

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "src" / "secure_enterprise_ai_assistant" / "resources" / "knowledge_base"
)


def main() -> None:
    write_knowledge_base(OUTPUT_DIRECTORY)


if __name__ == "__main__":
    main()
