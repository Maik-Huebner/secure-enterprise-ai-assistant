"""Every novabank-* command line is usable in German: help, usage line, errors, commands."""

from __future__ import annotations

import pytest

from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser, translate_error
from secure_enterprise_ai_assistant.evaluation import runner
from secure_enterprise_ai_assistant.mcp import server
from secure_enterprise_ai_assistant.observability import cli as langfuse_cli
from secure_enterprise_ai_assistant.rag import cli as index_cli
from secure_enterprise_ai_assistant.security import audit
from secure_enterprise_ai_assistant.security import cli as users_cli

ENGLISH_ARGPARSE_TEXT = ("usage:", "positional arguments", "options:", "show this help", "error:")


def _help(main: object, argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as stopped:
        main(argv)  # type: ignore[operator]
    assert stopped.value.code == 0
    return capsys.readouterr().out


@pytest.mark.parametrize(
    "main",
    [users_cli.main, index_cli.main, audit.main, langfuse_cli.main, server.main],
    ids=["users", "index", "audit", "langfuse", "mcp"],
)
def test_help_is_german(main: object, capsys: pytest.CaptureFixture[str]) -> None:
    text = _help(main, ["--hilfe"], capsys)
    assert text.startswith("Aufruf: ")
    assert "diese Hilfe anzeigen und beenden" in text
    assert not [phrase for phrase in ENGLISH_ARGPARSE_TEXT if phrase in text]


def test_evaluation_help_is_german(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["novabank-evaluate", "-h"])
    text = _help(lambda _argv: runner.main(), [], capsys)
    assert "Offline-Auswertung" in text and "--ausgabe" in text


def test_subcommands_have_german_names_and_keep_english_aliases(
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = _help(users_cli.main, ["-h"], capsys)
    assert "anlegen (add)" in text and "anzeigen (list)" in text and "loeschen (remove)" in text
    assert "neu-aufbauen (rebuild)" in _help(index_cli.main, ["-h"], capsys)
    assert "pruefen (verify)" in _help(audit.main, ["-h"], capsys)
    langfuse = _help(langfuse_cli.main, ["-h"], capsys)
    assert "pruefen (check)" in langfuse and "einrichten (setup)" in langfuse


def test_errors_are_german(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        index_cli.main(["foo"])
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "Fehler: Angabe BEFEHL: ungültige Auswahl 'foo'" in error
    assert "möglich: neu-aufbauen" in error


@pytest.mark.parametrize(
    ("english", "german"),
    [
        ("the following arguments are required: NAME", "Folgende Angaben fehlen: NAME"),
        ("unrecognized arguments: --x", "Unbekannte Angaben: --x"),
        ("argument --port: invalid int value: 'abc'", "Angabe --port: ungültiger Wert 'abc'"),
        ("argument --pfad: expected one argument", "Angabe --pfad: erwartet genau einen Wert"),
        ("something new", "something new"),  # unknown messages pass through unchanged
    ],
)
def test_translate_error(english: str, german: str) -> None:
    assert translate_error(english) == german


def test_parser_without_help_option() -> None:
    parser = GermanArgumentParser(prog="x", add_help=False)
    assert "-h" not in parser._option_string_actions


def test_audit_cli_checks_the_chain_with_german_and_english_names(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    from secure_enterprise_ai_assistant.security import Principal, Role

    log = tmp_path / "audit.jsonl"
    audit.AuditLog(log).record("login", Principal(username="sb.nord", role=Role.CASE_WORKER))
    assert audit.main(["pruefen", "--pfad", str(log)]) == 0
    assert audit.main(["verify", "--path", str(log)]) == 0
    assert "Audit-Log intakt: 1 Einträge" in capsys.readouterr().out
