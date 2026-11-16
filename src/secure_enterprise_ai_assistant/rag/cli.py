"""Command line for the persistent knowledge index: ``novabank-index neu-aufbauen|status``."""

from __future__ import annotations

import json
import time

from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser
from secure_enterprise_ai_assistant.core.logs import configure_logging
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.rag.index_store import (
    expected_manifest,
    index_directory,
    read_manifest,
)
from secure_enterprise_ai_assistant.rag.ingestion import KnowledgeIngestor
from secure_enterprise_ai_assistant.rag.service import build_embedder, build_index
from secure_enterprise_ai_assistant.resources import KNOWLEDGE_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = GermanArgumentParser(
        prog="novabank-index", description="Persistenten Suchindex verwalten."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "neu-aufbauen", aliases=["rebuild"], help="Index aus der Wissensbasis neu berechnen"
    )
    commands.add_parser("status", help="Zustand des Index anzeigen")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    embedder = build_embedder(settings)
    if not embedder.is_semantic:
        print("Der Hashing-Embedder braucht keinen persistenten Index.")
        return 0
    chunks = KnowledgeIngestor(KNOWLEDGE_ROOT).ingest_directory()
    directory = index_directory(settings.resolved_index_dir, embedder.name)

    if args.command in {"neu-aufbauen", "rebuild"}:
        started = time.perf_counter()
        build_index(chunks, embedder, settings.resolved_index_dir)
        seconds = time.perf_counter() - started
        print(f"Index neu aufgebaut: {len(chunks)} Abschnitte, {embedder.name}, {seconds:.1f} s")
        print(f"Ordner: {directory}")
        return 0

    stored = read_manifest(directory)
    current = expected_manifest(chunks, embedder.name, dimension=0)
    status = {
        "embedder": embedder.name,
        "ordner": str(directory),
        "vorhanden": stored is not None,
        "aktuell": bool(stored and stored.matches(current)),
        "abschnitte": stored.chunk_count if stored else None,
        "erstellt": stored.created_at if stored else None,
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["aktuell"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
