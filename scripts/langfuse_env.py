"""Create deploy/langfuse/.env with fresh random secrets for the local Langfuse stack.

Usage: python scripts/langfuse_env.py [--force]

The file is git-ignored. It also contains the project keys that the assistant needs; the script
prints the three lines to copy into the project's own .env (never into the repository).
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser

TARGET = Path(__file__).resolve().parents[1] / "deploy" / "langfuse" / ".env"


def _hex(bytes_: int = 32) -> str:
    return secrets.token_hex(bytes_)


def main() -> None:
    parser = GermanArgumentParser(
        description="deploy/langfuse/.env mit frischen Zufallsschlüsseln für Langfuse anlegen."
    )
    parser.add_argument(
        "--ueberschreiben",
        "--force",
        dest="force",
        action="store_true",
        help="vorhandene Datei ersetzen (setzt alle Schlüssel neu)",
    )
    parser.add_argument(
        "--port", type=int, default=3000, metavar="PORT", help="Port der Langfuse-Oberfläche"
    )
    arguments = parser.parse_args()
    if TARGET.exists() and not arguments.force:
        sys.exit(
            f"{TARGET} gibt es schon; mit --ueberschreiben ersetzen (setzt alle Schlüssel neu)."
        )
    public_key = f"pk-lf-{_hex(16)}"
    secret_key = f"sk-lf-{_hex(16)}"
    values = {
        "POSTGRES_PASSWORD": _hex(16),
        "CLICKHOUSE_PASSWORD": _hex(16),
        "REDIS_AUTH": _hex(16),
        "MINIO_ROOT_PASSWORD": _hex(16),
        "SALT": _hex(16),
        "ENCRYPTION_KEY": _hex(32),  # 64 hex characters, as Langfuse requires
        "NEXTAUTH_SECRET": _hex(32),
        "LANGFUSE_PUBLIC_KEY": public_key,
        "LANGFUSE_SECRET_KEY": secret_key,
        "LANGFUSE_INIT_USER_PASSWORD": secrets.token_urlsafe(18),
        "LANGFUSE_PORT": str(arguments.port),
    }
    TARGET.write_text(
        "# Erzeugt von scripts/langfuse_env.py – lokale Geheimnisse, niemals einchecken.\n"
        + "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )
    TARGET.chmod(0o600)
    print(f"{TARGET} geschrieben (nur für den Besitzer lesbar).")
    print("Zum Einschalten des Tracings in die .env des Projekts übernehmen:")
    print("  LANGFUSE_ENABLED=true")
    print(f"  LANGFUSE_BASE_URL=http://localhost:{arguments.port}")
    print(f"  LANGFUSE_PUBLIC_KEY={public_key}")
    print("  LANGFUSE_SECRET_KEY=<Wert von LANGFUSE_SECRET_KEY aus deploy/langfuse/.env>")
    print("Anmeldung in Langfuse: admin@novabank.example, Passwort steht in deploy/langfuse/.env.")


if __name__ == "__main__":
    main()
