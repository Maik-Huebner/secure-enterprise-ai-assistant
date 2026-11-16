"""Persistent FAISS index with a manifest that guards against stale or mismatched indexes."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import faiss
import numpy as np
from pydantic import BaseModel, ConfigDict

from secure_enterprise_ai_assistant.core.logs import get_logger
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeChunk

logger = get_logger(__name__)

INDEX_SCHEMA_VERSION = 1
# Bump when ingestion/chunking changes so that existing indexes are rebuilt.
CHUNKER_VERSION = "3"

_MANIFEST = "manifest.json"
_CHUNKS = "chunks.json"
_VECTORS = "vectors.faiss"


class IndexManifest(BaseModel):
    """Everything that must match before a stored index may be reused."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = INDEX_SCHEMA_VERSION
    chunker_version: str = CHUNKER_VERSION
    embedder: str
    dimension: int
    corpus_sha256: str
    chunk_count: int
    created_at: str

    def matches(self, other: IndexManifest) -> bool:
        fields = ("schema_version", "chunker_version", "embedder", "corpus_sha256")
        return all(getattr(self, field) == getattr(other, field) for field in fields)


def corpus_fingerprint(chunks: list[KnowledgeChunk]) -> str:
    """Hash the exact chunk content and metadata that the index is built from."""
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.model_dump_json().encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def index_directory(root: Path, embedder_name: str) -> Path:
    """Return the per-embedder index folder below ``root``."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", embedder_name.casefold()).strip("-")
    return root / slug


def expected_manifest(
    chunks: list[KnowledgeChunk], embedder_name: str, dimension: int
) -> IndexManifest:
    return IndexManifest(
        embedder=embedder_name,
        dimension=dimension,
        corpus_sha256=corpus_fingerprint(chunks),
        chunk_count=len(chunks),
        created_at=datetime.now(tz=UTC).isoformat(),
    )


def save_index(
    directory: Path, chunks: list[KnowledgeChunk], vectors: np.ndarray, manifest: IndexManifest
) -> None:
    """Write vectors, chunks, and manifest; the manifest is written last."""
    directory.mkdir(parents=True, exist_ok=True)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(directory / _VECTORS))
    (directory / _CHUNKS).write_text(
        json.dumps([chunk.model_dump(mode="json") for chunk in chunks], ensure_ascii=False),
        encoding="utf-8",
    )
    (directory / _MANIFEST).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        "knowledge_index_saved",
        extra={"embedder": manifest.embedder, "chunks": manifest.chunk_count},
    )


def read_manifest(directory: Path) -> IndexManifest | None:
    path = directory / _MANIFEST
    if not path.is_file():
        return None
    try:
        return IndexManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def load_index(directory: Path, expected: IndexManifest) -> np.ndarray | None:
    """Return stored vectors if the manifest matches ``expected``; otherwise ``None``."""
    stored = read_manifest(directory)
    if stored is None or not stored.matches(expected) or stored.chunk_count != expected.chunk_count:
        if stored is not None:
            logger.info("knowledge_index_stale", extra={"embedder": expected.embedder})
        return None
    index = faiss.read_index(str(directory / _VECTORS))
    if index.ntotal != expected.chunk_count:
        return None
    vectors = np.zeros((index.ntotal, index.d), dtype="float32")
    for position in range(index.ntotal):
        vectors[position] = index.reconstruct(position)
    logger.info("knowledge_index_loaded", extra={"embedder": stored.embedder})
    return vectors
