"""Identity models shared by the API, the MCP tools and the audit log."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    """Roles of the fictional NovaBank credit department."""

    CASE_WORKER = "sachbearbeiter"
    REVIEWER = "pruefer"
    ADMIN = "admin"


class Principal(BaseModel):
    """The authenticated caller on whose behalf every check is made."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    role: Role | None
    team: str | None = None

    @classmethod
    def anonymous(cls) -> Principal:
        """A caller without any rights (no or invalid token)."""
        return cls(username="anonym", role=None)

    @classmethod
    def system(cls) -> Principal:
        """Explicit full-rights identity for offline evaluation and maintenance scripts."""
        return cls(username="system", role=Role.ADMIN)

    @property
    def is_authenticated(self) -> bool:
        return self.role is not None


class UserRecord(BaseModel):
    """One stored user. Only an Argon2id hash is kept, never the password."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(pattern=r"^[a-z0-9._-]{3,64}$")
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    team: str | None = Field(default=None, pattern=r"^[a-z0-9-]{2,40}$")
    password_hash: str = Field(min_length=20)
    active: bool = True

    def principal(self) -> Principal:
        return Principal(username=self.username, role=self.role, team=self.team)
