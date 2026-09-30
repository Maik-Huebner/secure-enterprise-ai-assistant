"""Facade for building and querying the local NovaBank knowledge index."""

from __future__ import annotations

from pathlib import Path

from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.rag.ingestion import KnowledgeIngestor
from secure_enterprise_ai_assistant.rag.retrieval import Embedder, HybridRetriever
from secure_enterprise_ai_assistant.resources import KNOWLEDGE_ROOT

DEFAULT_KNOWLEDGE_ROOT = KNOWLEDGE_ROOT


class KnowledgeService:
    """Expose safe retrieval while preserving source metadata."""

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    @classmethod
    def from_directory(
        cls,
        knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
        embedder: Embedder | None = None,
    ) -> KnowledgeService:
        chunks = KnowledgeIngestor(knowledge_root).ingest_directory()
        return cls(HybridRetriever(chunks, embedder=embedder))

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, str] | None = None,
    ) -> KnowledgeSearchResponse:
        return self._retriever.search(query, top_k=top_k, metadata_filter=metadata_filter)
