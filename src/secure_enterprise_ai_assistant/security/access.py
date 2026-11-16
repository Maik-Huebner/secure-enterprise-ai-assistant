"""Authorization rules enforced in code and in every MCP tool, never in a prompt.

| Role            | Cases            | Documents              | Decision brief |
|-----------------|------------------|------------------------|----------------|
| sachbearbeiter  | own team only    | intern                 | no             |
| pruefer         | all              | intern + vertraulich   | yes            |
| admin           | all              | intern + vertraulich   | yes            |
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from secure_enterprise_ai_assistant.resources import CASE_ASSIGNMENTS_PATH
from secure_enterprise_ai_assistant.security.models import Principal, Role

_CASE_NUMBER = re.compile(r"^CASE-(\d{5})$")
DOCUMENT_CLASSES_BY_ROLE: dict[Role, frozenset[str]] = {
    Role.CASE_WORKER: frozenset({"intern"}),
    Role.REVIEWER: frozenset({"intern", "vertraulich"}),
    Role.ADMIN: frozenset({"intern", "vertraulich"}),
}


class AccessDeniedError(PermissionError):
    """Raised when the principal may not perform an action (message is safe to show)."""


class AccessPolicy:
    """Role- and team-based access to cases, documents and actions."""

    def __init__(self, team_ranges: dict[str, tuple[int, int]]) -> None:
        self._team_ranges = team_ranges

    @classmethod
    def from_json(cls, path: Path = CASE_ASSIGNMENTS_PATH) -> AccessPolicy:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            {
                team: (int(bounds["first_case"]), int(bounds["last_case"]))
                for team, bounds in payload["teams"].items()
            }
        )

    @property
    def teams(self) -> list[str]:
        return sorted(self._team_ranges)

    def team_of(self, case_id: str) -> str | None:
        match = _CASE_NUMBER.match(case_id)
        if not match:
            return None
        number = int(match.group(1))
        for team, (first, last) in self._team_ranges.items():
            if first <= number <= last:
                return team
        return None

    def can_read_case(self, principal: Principal, case_id: str) -> bool:
        if principal.role in {Role.REVIEWER, Role.ADMIN}:
            return True
        if principal.role == Role.CASE_WORKER:
            return principal.team is not None and self.team_of(case_id) == principal.team
        return False

    def readable_case_ids(self, principal: Principal, case_ids: Iterable[str]) -> list[str]:
        return [case_id for case_id in case_ids if self.can_read_case(principal, case_id)]

    def document_classes(self, principal: Principal) -> frozenset[str]:
        if principal.role is None:
            return frozenset()
        return DOCUMENT_CLASSES_BY_ROLE[principal.role]

    def can_search_knowledge(self, principal: Principal) -> bool:
        return bool(self.document_classes(principal))

    def can_request_decision_brief(self, principal: Principal) -> bool:
        return principal.role in {Role.REVIEWER, Role.ADMIN}

    def can_read_audit_log(self, principal: Principal) -> bool:
        return principal.role == Role.ADMIN

    def require_decision_brief(self, principal: Principal) -> None:
        if not self.can_request_decision_brief(principal):
            raise AccessDeniedError(
                "Eine Entscheidungsvorlage dürfen nur Prüferinnen und Prüfer anfordern "
                "(Vier-Augen-Prinzip)."
            )
