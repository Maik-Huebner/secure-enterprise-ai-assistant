"""User store, Argon2id hashing and the users CLI."""

from __future__ import annotations

import stat

import pytest

from secure_enterprise_ai_assistant.security import cli
from secure_enterprise_ai_assistant.security.models import Role
from secure_enterprise_ai_assistant.security.passwords import (
    WeakPasswordError,
    hash_password,
    verify_password,
)
from secure_enterprise_ai_assistant.security.users import UserStore

PASSWORD = "Testpasswort-Einheit-2026"


def test_argon2id_hashes_are_salted_and_verifiable() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)

    assert first.startswith("$argon2id$")
    assert first != second
    assert verify_password(first, PASSWORD)
    assert not verify_password(first, PASSWORD + "x")
    assert not verify_password(None, PASSWORD)
    assert not verify_password("kein-hash", PASSWORD)


def test_weak_passwords_are_rejected() -> None:
    with pytest.raises(WeakPasswordError):
        hash_password("kurz")


def test_store_keeps_only_hashes_with_owner_only_permissions(tmp_path) -> None:
    store = UserStore(tmp_path / "users.json")
    store.add("anna.becker", PASSWORD, Role.REVIEWER, "Anna Becker")
    text = store.path.read_text(encoding="utf-8")

    assert PASSWORD not in text
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    principal = store.authenticate("anna.becker", PASSWORD)
    assert principal is not None and principal.role == Role.REVIEWER
    assert store.authenticate("anna.becker", "falsch-falsch-falsch") is None
    assert store.authenticate("unbekannt", PASSWORD) is None


def test_store_rules(tmp_path) -> None:
    store = UserStore(tmp_path / "users.json")
    store.add("anna.becker", PASSWORD, Role.ADMIN, "Anna")

    with pytest.raises(ValueError, match="existiert bereits"):
        store.add("anna.becker", PASSWORD, Role.ADMIN, "Anna")
    with pytest.raises(ValueError, match="Team"):
        store.add("ohne.team", PASSWORD, Role.CASE_WORKER, "Ohne Team")
    assert store.remove("anna.becker") is True
    assert store.remove("anna.becker") is False


def test_users_cli_prompts_for_the_password(tmp_path, monkeypatch, capsys) -> None:
    from secure_enterprise_ai_assistant.core.settings import Settings

    settings = Settings.model_validate({"users_file": tmp_path / "users.json"})
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: PASSWORD)

    assert (
        cli.main(["anlegen", "max.muster", "--rolle", "sachbearbeiter", "--team", "team-nord"]) == 0
    )
    assert cli.main(["anzeigen"]) == 0
    output = capsys.readouterr().out
    assert "max.muster" in output and "team-nord" in output
    assert PASSWORD not in output


def test_users_cli_reads_the_password_from_stdin(tmp_path, monkeypatch, capsys) -> None:
    import io

    from secure_enterprise_ai_assistant.core.settings import Settings

    settings = Settings.model_validate({"users_file": tmp_path / "users.json"})
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))

    # The English names from v2.0.0 remain as aliases.
    assert cli.main(["add", "anna.becker", "--role", "pruefer", "--password-stdin"]) == 0
    assert PASSWORD not in capsys.readouterr().out
    assert PASSWORD not in (tmp_path / "users.json").read_text()
