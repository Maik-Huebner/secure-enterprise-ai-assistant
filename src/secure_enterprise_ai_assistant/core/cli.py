"""German command lines: help, usage line and error messages of ``argparse`` in German.

``argparse`` only ships English texts. This parser replaces the visible parts (usage line,
section titles, ``-h`` and the common error messages) so that every ``novabank-*`` command can
be used in German. Subcommands get German names; the earlier English names stay as aliases so
that existing scripts keep working.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from typing import Any, NoReturn

# English argparse error messages (Python 3.13) and their German counterparts.
_ERROR_TRANSLATIONS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), replacement)
    for pattern, replacement in (
        (r"^the following arguments are required: (.+)$", r"Folgende Angaben fehlen: \1"),
        (r"^unrecognized arguments: (.+)$", r"Unbekannte Angaben: \1"),
        (r"^one of the arguments (.+) is required$", r"Eine dieser Angaben ist nötig: \1"),
        (r"^ambiguous option: (.+) could match (.+)$", r"Mehrdeutige Option \1 (passt zu \2)"),
        (
            r"^argument (.+?): invalid choice: (.+) \(choose from (.+)\)$",
            r"Angabe \1: ungültige Auswahl \2 (möglich: \3)",
        ),
        (r"^argument (.+?): invalid \w+ value: (.+)$", r"Angabe \1: ungültiger Wert \2"),
        (r"^argument (.+?): expected one argument$", r"Angabe \1: erwartet genau einen Wert"),
        (
            r"^argument (.+?): expected at least one argument$",
            r"Angabe \1: erwartet mindestens einen Wert",
        ),
        (
            r"^argument (.+?): not allowed with argument (.+)$",
            r"Angabe \1: nicht zusammen mit \2 erlaubt",
        ),
        (r"^argument (.+?): ignored explicit argument (.+)$", r"Angabe \1: Wert \2 nicht erlaubt"),
    )
)


def translate_error(message: str) -> str:
    """Return the German version of a known ``argparse`` error message."""
    for pattern, replacement in _ERROR_TRANSLATIONS:
        if pattern.match(message):
            return pattern.sub(replacement, message)
    return message


class GermanHelpFormatter(argparse.HelpFormatter):
    """Prints ``Aufruf:`` instead of ``usage:``."""

    def add_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: str | None = None,
    ) -> None:
        super().add_usage(usage, actions, groups, prefix="Aufruf: " if prefix is None else prefix)


class GermanArgumentParser(argparse.ArgumentParser):
    """``ArgumentParser`` with German help, section titles and error messages."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", GermanHelpFormatter)
        add_help = kwargs.pop("add_help", True)
        kwargs["add_help"] = False  # replaced below by a German -h
        super().__init__(*args, **kwargs)
        self._positionals.title = "Angaben"
        self._optionals.title = "Optionen"
        if add_help:
            self.add_argument(
                "-h", "--hilfe", "--help", action="help", help="diese Hilfe anzeigen und beenden"
            )

    def add_subparsers(self, **kwargs: Any) -> Any:
        kwargs.setdefault("title", "Befehle")
        kwargs.setdefault("metavar", "BEFEHL")
        return super().add_subparsers(**kwargs)

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: Fehler: {translate_error(message)}\n")
