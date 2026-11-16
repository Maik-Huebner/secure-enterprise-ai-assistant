"""Command line for the persistent knowledge index: ``novabank-index rebuild|status``."""

from __future__ import annotations

import argparse
import json
import time

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
    parser = argparse.ArgumentParser(description="Persistenten Suchindex verwalten.")
    parser.add_argument("command", choices=("rebuild", "status"))
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    embedder = build_embedder(settings)
    if not embedder.is_semantic:
        print("Der Hashing-Embedder braucht keinen persistenten Index.")
        return 0
    chunks = KnowledgeIngestor(KNOWLEDGE_ROOT).ingest_directory()
    directory = index_directory(settings.resolved_index_dir, embedder.name)

    if args.command == "rebuild":
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
