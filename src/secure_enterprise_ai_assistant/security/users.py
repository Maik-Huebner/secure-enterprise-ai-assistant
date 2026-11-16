"""User store in the runtime directory (never in the repository)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from secure_enterprise_ai_assistant.security.models import Principal, Role, UserRecord
from secure_enterprise_ai_assistant.security.passwords import hash_password, verify_password


class UserStore:
    """JSON file of users with Argon2id hashes; written with owner-only permissions."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, UserRecord]:
        if not self.path.is_file():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        records = (UserRecord.model_validate(item) for item in payload.get("users", []))
        return {record.username: record for record in records}

    def _save(self, users: dict[str, UserRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"users": [user.model_dump(mode="json") for user in users.values()]},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def list_users(self) -> list[UserRecord]:
        return sorted(self._load().values(), key=lambda user: user.username)

    def add(
        self,
        username: str,
        password: str,
        role: Role,
        display_name: str,
        team: str | None = None,
    ) -> UserRecord:
        users = self._load()
        if username in users:
            raise ValueError(f"Benutzer {username} existiert bereits.")
        if role == Role.CASE_WORKER and not team:
            raise ValueError("Sachbearbeiterinnen und Sachbearbeiter brauchen ein Team.")
        record = UserRecord(
            username=username,
            display_name=display_name,
            role=role,
            team=team,
            password_hash=hash_password(password),
        )
        users[username] = record
        self._save(users)
        return record

    def remove(self, username: str) -> bool:
        users = self._load()
        if users.pop(username, None) is None:
            return False
        self._save(users)
        return True

    def authenticate(self, username: str, password: str) -> Principal | None:
        """Return the principal for valid credentials; ``None`` otherwise (same timing)."""
        record = self._load().get(username)
        password_hash = record.password_hash if record and record.active else None
        if not verify_password(password_hash, password) or record is None:
            return None
        return record.principal()
