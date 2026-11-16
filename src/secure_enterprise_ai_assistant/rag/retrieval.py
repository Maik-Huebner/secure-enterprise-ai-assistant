"""Hybrid FAISS and BM25S retrieval with metadata filtering."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

import bm25s
import faiss
import numpy as np
from bm25s.stopwords import STOPWORDS_GERMAN

from secure_enterprise_ai_assistant.core.logs import get_logger
from secure_enterprise_ai_assistant.models.knowledge import (
    KnowledgeChunk,
    KnowledgeSearchResponse,
    RetrievalResult,
)

logger = get_logger(__name__)

TOKEN_PATTERN = re.compile(r"(?u)\b\w\w+\b")
# German stopwords: knowledge base and questions are both German.
SEARCH_STOPWORDS = list(STOPWORDS_GERMAN)


class Embedder(Protocol):
    """Minimal embedding interface used by the local retriever."""

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return normalized float32 embeddings."""


class HashingEmbedder:
    """Dependency-free deterministic embedder for tests and offline bootstrap."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimensions), dtype="float32")
        for row, text in enumerate(texts):
            for token in TOKEN_PATTERN.findall(text.casefold()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                index = int.from_bytes(digest, "little") % self.dimensions
                vectors[row, index] += 1.0
        faiss.normalize_L2(vectors)
        return vectors


class SentenceTransformerEmbedder:
    """Production embedder backed by a locally available Sentence Transformer."""

    def __init__(self, model_name_or_path: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name_or_path, local_files_only=True)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        values = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(values, dtype="float32")


class HybridRetriever:
    """Fuse dense FAISS and lexical BM25S rankings using reciprocal rank fusion."""

    def __init__(
        self,
        chunks: Sequence[KnowledgeChunk],
        embedder: Embedder | None = None,
        relevance_threshold: float = 0.014,
    ) -> None:
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("Die Textabschnitte der Wissensbasis brauchen eindeutige IDs.")
        flagged_documents = {chunk.document_id for chunk in chunks if chunk.security_flags}
        if flagged_documents:
            logger.warning(
                "knowledge_documents_quarantined",
                extra={
                    "document_ids": sorted(flagged_documents),
                    "flags": sorted({flag for chunk in chunks for flag in chunk.security_flags}),
                },
            )
        safe_chunks = [chunk for chunk in chunks if chunk.document_id not in flagged_documents]
        if not safe_chunks:
            raise ValueError("Es wird mindestens ein Textabschnitt der Wissensbasis benötigt.")
        self._chunks = safe_chunks
        self._embedder = embedder or HashingEmbedder()
        self._require_lexical_evidence = isinstance(self._embedder, HashingEmbedder)
        self._relevance_threshold = relevance_threshold
        corpus = [self._searchable_text(chunk) for chunk in self._chunks]
        embeddings = self._embedder.encode(corpus)
        self._faiss = faiss.IndexFlatIP(embeddings.shape[1])
        self._faiss.add(embeddings)
        self._bm25 = bm25s.BM25()
        self._bm25.index(
            bm25s.tokenize(corpus, stopwords=SEARCH_STOPWORDS, show_progress=False),
            show_progress=False,
        )

    def document_ids(self) -> list[str]:
        """Return the sorted IDs of all indexed (non-quarantined) documents."""
        return sorted({chunk.document_id for chunk in self._chunks})

    @staticmethod
    def _searchable_text(chunk: KnowledgeChunk) -> str:
        return f"{chunk.title} {chunk.section} {chunk.content}"

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, str] | None = None,
    ) -> KnowledgeSearchResponse:
        """Return ranked, attributable results and reject weak out-of-scope matches."""
        normalized_query = query.strip()
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError("top_k muss eine ganze Zahl zwischen 1 und 100 sein.")
        if len(normalized_query) < 3:
            return KnowledgeSearchResponse(query=query, results=[], out_of_scope=True)
        candidate_count = len(self._chunks)
        semantic_scores, semantic_indices = self._faiss.search(
            self._embedder.encode([normalized_query]), candidate_count
        )
        lexical_indices, lexical_scores = self._bm25.retrieve(
            bm25s.tokenize([normalized_query], stopwords=SEARCH_STOPWORDS, show_progress=False),
            k=candidate_count,
            show_progress=False,
        )
        semantic_rank = {int(index): rank for rank, index in enumerate(semantic_indices[0], 1)}
        lexical_rank = {int(index): rank for rank, index in enumerate(lexical_indices[0], 1)}
        semantic_raw = {
            int(index): float(score)
            for index, score in zip(semantic_indices[0], semantic_scores[0], strict=True)
        }
        lexical_raw = {
            int(index): float(score)
            for index, score in zip(lexical_indices[0], lexical_scores[0], strict=True)
        }

        results: list[RetrievalResult] = []
        for index, chunk in enumerate(self._chunks):
            if metadata_filter and any(
                str(getattr(chunk, key, "")) != value for key, value in metadata_filter.items()
            ):
                continue
            combined = (0.55 / (60 + semantic_rank[index])) + (0.45 / (60 + lexical_rank[index]))
            results.append(
                RetrievalResult(
                    chunk=chunk,
                    semantic_score=semantic_raw[index],
                    lexical_score=lexical_raw[index],
                    combined_score=combined,
                )
            )
        results.sort(key=lambda item: item.combined_score, reverse=True)
        selected = results[:top_k]
        has_lexical_evidence = any(item.lexical_score > 0 for item in selected)
        has_semantic_evidence = any(item.semantic_score >= 0.15 for item in selected)
        evidence_found = has_lexical_evidence or (
            has_semantic_evidence and not self._require_lexical_evidence
        )
        in_scope = bool(selected) and evidence_found
        if selected and selected[0].combined_score < self._relevance_threshold:
            in_scope = False
        return KnowledgeSearchResponse(
            query=normalized_query,
            results=selected if in_scope else [],
            out_of_scope=not in_scope,
        )
