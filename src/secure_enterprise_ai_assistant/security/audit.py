"""Append-only audit log with a SHA-256 hash chain (tampering becomes detectable).

Each line is a JSON object with ``prev_hash`` and ``hash``. Changing, deleting or reordering a
line breaks the chain from that point on; ``novabank-audit verify`` reports where. This makes
tampering *evident*, not impossible: production systems additionally ship entries to
write-once storage.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser
from secure_enterprise_ai_assistant.core.logs import current_request_id
from secure_enterprise_ai_assistant.security.models import Principal

GENESIS = "0" * 64


def _digest(previous: str, entry: dict[str, Any]) -> str:
    canonical = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{previous}\n{canonical}".encode()).hexdigest()


class AuditLog:
    """Thread-safe writer for the audit chain."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._last: str | None = None

    def _last_hash(self) -> str:
        if self._last is not None:
            return self._last
        if not self.path.is_file():
            return GENESIS
        last = GENESIS
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = json.loads(line)["hash"]
        return last

    def record(self, event: str, principal: Principal, **details: Any) -> None:
        """Append one event. Never pass free-text user input or document content here."""
        with self._lock:
            previous = self._last_hash()
            entry = {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "event": event,
                "user": principal.username,
                "role": principal.role.value if principal.role else None,
                "request_id": current_request_id(),
                "details": details,
                "prev_hash": previous,
            }
            digest = _digest(previous, entry)
            entry["hash"] = digest
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            self._last = digest


def verify_chain(path: Path) -> tuple[bool, int, int | None]:
    """Return (intact, number_of_entries, first_broken_line_or_None)."""
    if not path.is_file():
        return True, 0, None
    previous = GENESIS
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            entry = json.loads(line)
            stored = str(entry.pop("hash", ""))
            if entry.get("prev_hash") != previous or _digest(previous, entry) != stored:
                return False, count, line_number
            previous = stored
            count += 1
    return True, count, None


def main(argv: list[str] | None = None) -> int:
    from secure_enterprise_ai_assistant.core.settings import get_settings

    parser = GermanArgumentParser(prog="novabank-audit", description="Audit-Log prüfen.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "pruefen", aliases=["verify"], help="Hash-Kette des Audit-Logs prüfen"
    )
    check.add_argument(
        "--pfad",
        "--path",
        dest="path",
        type=Path,
        metavar="DATEI",
        help="anderes Audit-Log als in den Einstellungen",
    )
    args = parser.parse_args(argv)
    path = args.path or get_settings().resolved_audit_log
    intact, count, broken = verify_chain(path)
    if intact:
        print(f"Audit-Log intakt: {count} Einträge ({path}).")
        return 0
    print(f"Audit-Log MANIPULIERT oder beschädigt ab Zeile {broken} ({path}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
