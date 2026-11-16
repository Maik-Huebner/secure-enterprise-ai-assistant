"""Facade for building, persisting, and querying the local NovaBank knowledge index."""

from __future__ import annotations

import json
from collections.abc import Collection
from pathlib import Path

from secure_enterprise_ai_assistant.core.settings import Settings, get_settings
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeChunk, KnowledgeSearchResponse
from secure_enterprise_ai_assistant.rag.embeddings import (
    Embedder,
    HashingEmbedder,
    OllamaEmbedder,
    SentenceTransformerEmbedder,
)
from secure_enterprise_ai_assistant.rag.index_store import (
    expected_manifest,
    index_directory,
    load_index,
    save_index,
)
from secure_enterprise_ai_assistant.rag.ingestion import KnowledgeIngestor
from secure_enterprise_ai_assistant.rag.retrieval import HybridRetriever, searchable_text
from secure_enterprise_ai_assistant.resources import KNOWLEDGE_ROOT, RETRIEVAL_THRESHOLDS_PATH

DEFAULT_KNOWLEDGE_ROOT = KNOWLEDGE_ROOT


def build_embedder(settings: Settings | None = None) -> Embedder:
    """Create the embedder selected in the settings."""
    settings = settings or get_settings()
    if settings.embedding_backend == "hashing":
        return HashingEmbedder()
    if settings.embedding_backend == "sentence_transformers":
        return SentenceTransformerEmbedder(settings.embedding_model)
    return OllamaEmbedder(
        settings.embedding_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def calibrated_threshold(embedder_name: str) -> float | None:
    """Return the out-of-scope threshold calibrated on the dev split, if one exists."""
    if not RETRIEVAL_THRESHOLDS_PATH.is_file():
        return None
    thresholds = json.loads(RETRIEVAL_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    value = thresholds.get("min_semantic_score", {}).get(embedder_name)
    return float(value) if value is not None else None


def build_index(chunks: list[KnowledgeChunk], embedder: Embedder, index_root: Path) -> None:
    """Embed every chunk and write a fresh persistent index for ``embedder``."""
    vectors = embedder.encode_documents([searchable_text(chunk) for chunk in chunks])
    save_index(
        index_directory(index_root, embedder.name),
        chunks,
        vectors,
        expected_manifest(chunks, embedder.name, int(vectors.shape[1])),
    )


class KnowledgeService:
    """Expose safe retrieval while preserving source metadata."""

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    @classmethod
    def from_directory(
        cls,
        knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
        embedder: Embedder | None = None,
        index_root: Path | None = None,
        min_semantic_score: float | None = None,
    ) -> KnowledgeService:
        """Ingest the knowledge root and reuse a matching persistent index if available."""
        embedder = embedder or HashingEmbedder()
        chunks = KnowledgeIngestor(knowledge_root).ingest_directory()
        threshold = (
            min_semantic_score
            if min_semantic_score is not None
            else calibrated_threshold(embedder.name)
        )
        vectors = None
        # Hashing is cheap and deterministic; persisting it would add no value.
        if index_root is not None and embedder.is_semantic:
            directory = index_directory(index_root, embedder.name)
            probe = expected_manifest(chunks, embedder.name, dimension=0)
            vectors = load_index(directory, probe)
            if vectors is None:
                build_index(chunks, embedder, index_root)
                vectors = load_index(directory, probe)
        return cls(
            HybridRetriever(
                chunks, embedder=embedder, vectors=vectors, min_semantic_score=threshold
            )
        )

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> KnowledgeService:
        settings = settings or get_settings()
        return cls.from_directory(
            embedder=build_embedder(settings), index_root=settings.resolved_index_dir
        )

    @property
    def embedder_name(self) -> str:
        return self._retriever.embedder_name

    def document_ids(self) -> list[str]:
        """Return the IDs of all documents currently in the search index."""
        return self._retriever.document_ids()

    def document_classes(self) -> dict[str, str]:
        """Return the classification ('intern' or 'vertraulich') of every indexed document."""
        return self._retriever.document_classes()

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, str] | None = None,
        allowed_document_ids: Collection[str] | None = None,
    ) -> KnowledgeSearchResponse:
        return self._retriever.search(
            query,
            top_k=top_k,
            metadata_filter=metadata_filter,
            allowed_document_ids=allowed_document_ids,
        )
