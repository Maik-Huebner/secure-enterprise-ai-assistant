"""Manage API users: ``novabank-users add|list|remove``.

Passwords are prompted (or read from stdin with ``--password-stdin``), never stored or accepted
as command-line arguments.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.security.models import Role
from secure_enterprise_ai_assistant.security.passwords import WeakPasswordError
from secure_enterprise_ai_assistant.security.users import UserStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benutzer der NovaBank-API verwalten.")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Benutzer anlegen (Passwort wird verdeckt abgefragt)")
    add.add_argument("username")
    add.add_argument("--role", choices=[role.value for role in Role], required=True)
    add.add_argument("--team", help="Pflicht für sachbearbeiter, z. B. team-nord")
    add.add_argument("--name", dest="display_name", help="Anzeigename")
    add.add_argument(
        "--password-stdin",
        action="store_true",
        help="Passwort aus der ersten Zeile der Standardeingabe lesen (für Skripte)",
    )
    commands.add_parser("list", help="Benutzer anzeigen")
    remove = commands.add_parser("remove", help="Benutzer löschen")
    remove.add_argument("username")
    args = parser.parse_args(argv)

    store = UserStore(get_settings().resolved_users_file)
    if args.command == "list":
        for user in store.list_users():
            team = user.team or "-"
            print(f"{user.username:<20} {user.role.value:<15} {team:<12} {user.display_name}")
        return 0
    if args.command == "remove":
        removed = store.remove(args.username)
        print("Gelöscht." if removed else "Benutzer nicht gefunden.")
        return 0 if removed else 1

    if args.password_stdin:
        # Never as an argument: command lines are visible in the process list and shell history.
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Passwort (mind. 12 Zeichen): ")
        if password != getpass.getpass("Passwort wiederholen: "):
            print("Die Passwörter stimmen nicht überein.")
            return 1
    try:
        record = store.add(
            args.username,
            password,
            Role(args.role),
            display_name=args.display_name or args.username,
            team=args.team,
        )
    except (ValueError, WeakPasswordError) as exc:
        print(exc)
        return 1
    print(f"Benutzer {record.username} ({record.role.value}) angelegt in {store.path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
