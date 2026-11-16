"""Hybrid FAISS + BM25S retrieval with pre-ranking filters and calibrated scope rejection."""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence

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
from secure_enterprise_ai_assistant.rag.embeddings import (
    Embedder,
    HashingEmbedder,
    OllamaEmbedder,
    SentenceTransformerEmbedder,
)

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "HybridRetriever",
    "OllamaEmbedder",
    "SentenceTransformerEmbedder",
]

logger = get_logger(__name__)

# German stopwords: knowledge base and questions are both German.
SEARCH_STOPWORDS = list(STOPWORDS_GERMAN)
RRF_K = 60
SEMANTIC_WEIGHT = 0.55
LEXICAL_WEIGHT = 0.45
# Explicitly named documents and sections always outrank fused scores (which stay below 0.02).
SECTION_BONUS = 1.0
DOCUMENT_BONUS = 0.5
BM25_CACHE_SIZE = 64
DOCUMENT_ID_PATTERN = re.compile(r"\bNB-[A-Z]{3}-\d{3}\b", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"\b(?:abschnitt|section|ziffer)\s+(\d+(?:\.\d+)*)\b", re.IGNORECASE)
# Used only when no calibrated threshold exists for a semantic embedder.
DEFAULT_MIN_SEMANTIC_SCORE = 0.5


def searchable_text(chunk: KnowledgeChunk) -> str:
    """Text that is embedded and lexically indexed for one chunk."""
    return f"{chunk.document_id} {chunk.title} – {chunk.section}\n{chunk.content}"


def section_number(section: str) -> str:
    """Return the leading section number of a heading such as '7.4 Harte …'."""
    head = section.split(" ", 1)[0]
    return head if head[:1].isdigit() else ""


class HybridRetriever:
    """Fuse vector (FAISS) and lexical (BM25S) rankings with reciprocal rank fusion.

    Filters are applied *before* ranking: only permitted chunks are scored and ranked, so
    hidden documents cannot influence rank positions or the out-of-scope decision.
    """

    def __init__(
        self,
        chunks: Sequence[KnowledgeChunk],
        embedder: Embedder | None = None,
        vectors: np.ndarray | None = None,
        min_semantic_score: float | None = None,
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
        safe_positions = [
            position
            for position, chunk in enumerate(chunks)
            if chunk.document_id not in flagged_documents
        ]
        if not safe_positions:
            raise ValueError("Es wird mindestens ein Textabschnitt der Wissensbasis benötigt.")
        self._chunks = [chunks[position] for position in safe_positions]
        self._embedder: Embedder = embedder or HashingEmbedder()
        self._relevance_threshold = relevance_threshold
        self._min_semantic_score = (
            min_semantic_score if min_semantic_score is not None else DEFAULT_MIN_SEMANTIC_SCORE
        )
        corpus = [searchable_text(chunk) for chunk in self._chunks]
        if vectors is None:
            embedded = self._embedder.encode_documents(corpus)
        else:
            if len(vectors) != len(chunks):
                raise ValueError("Anzahl der Vektoren passt nicht zur Anzahl der Textabschnitte.")
            embedded = np.ascontiguousarray(vectors[safe_positions], dtype="float32")
        self.vectors = embedded
        self._faiss = faiss.IndexFlatIP(embedded.shape[1])
        self._faiss.add(embedded)
        self._corpus = corpus
        self._bm25_cache: dict[tuple[int, ...], bm25s.BM25] = {}
        self._full_positions = tuple(range(len(self._chunks)))
        self._bm25_for(self._full_positions)

    def _bm25_for(self, positions: tuple[int, ...]) -> bm25s.BM25:
        """BM25 over exactly the permitted chunks.

        Term statistics (IDF, average length) are computed on the permitted subset only;
        otherwise hidden documents would still shift the ranking of visible ones.
        """
        cached = self._bm25_cache.get(positions)
        if cached is not None:
            return cached
        if len(self._bm25_cache) >= BM25_CACHE_SIZE:
            self._bm25_cache.pop(next(iter(self._bm25_cache)))
        model = bm25s.BM25()
        model.index(
            bm25s.tokenize(
                [self._corpus[index] for index in positions],
                stopwords=SEARCH_STOPWORDS,
                show_progress=False,
            ),
            show_progress=False,
        )
        self._bm25_cache[positions] = model
        return model

    @property
    def embedder_name(self) -> str:
        return self._embedder.name

    @property
    def chunks(self) -> list[KnowledgeChunk]:
        return list(self._chunks)

    def document_ids(self) -> list[str]:
        """Return the sorted IDs of all indexed (non-quarantined) documents."""
        return sorted({chunk.document_id for chunk in self._chunks})

    def _permitted_positions(
        self,
        metadata_filter: dict[str, str] | None,
        allowed_document_ids: Collection[str] | None,
    ) -> list[int]:
        positions = []
        for position, chunk in enumerate(self._chunks):
            if allowed_document_ids is not None and chunk.document_id not in allowed_document_ids:
                continue
            if metadata_filter and any(
                str(getattr(chunk, key, "")) != value for key, value in metadata_filter.items()
            ):
                continue
            positions.append(position)
        return positions

    def _semantic_ranking(self, query: str, positions: list[int]) -> list[tuple[int, float]]:
        query_vector = self._embedder.encode_queries([query])
        selector = faiss.IDSelectorBatch(np.asarray(positions, dtype="int64"))
        params = faiss.SearchParameters()
        params.sel = selector
        scores, indices = self._faiss.search(query_vector, len(positions), params=params)
        return [
            (int(index), float(score))
            for index, score in zip(indices[0], scores[0], strict=True)
            if index >= 0
        ]

    def _lexical_ranking(self, query: str, positions: list[int]) -> list[tuple[int, float]]:
        subset = tuple(positions)
        model = self._bm25_for(subset)
        indices, scores = model.retrieve(
            bm25s.tokenize([query], stopwords=SEARCH_STOPWORDS, show_progress=False),
            k=len(subset),
            show_progress=False,
        )
        return [
            (subset[int(index)], float(score))
            for index, score in zip(indices[0], scores[0], strict=True)
        ]

    def _identifier_bonus(self, query: str, positions: list[int]) -> dict[int, float]:
        """Bonus for chunks of explicitly mentioned documents; the named section scores highest."""
        document_ids = {match.upper() for match in DOCUMENT_ID_PATTERN.findall(query)}
        if not document_ids:
            return {}
        sections = set(SECTION_PATTERN.findall(query))
        return {
            index: (
                SECTION_BONUS
                if section_number(self._chunks[index].section) in sections
                else DOCUMENT_BONUS
            )
            for index in positions
            if self._chunks[index].document_id in document_ids
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, str] | None = None,
        allowed_document_ids: Collection[str] | None = None,
    ) -> KnowledgeSearchResponse:
        """Return ranked, attributable results and reject weak out-of-scope matches."""
        normalized_query = query.strip()
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError("top_k muss eine ganze Zahl zwischen 1 und 100 sein.")
        positions = self._permitted_positions(metadata_filter, allowed_document_ids)
        if len(normalized_query) < 3 or not positions:
            return KnowledgeSearchResponse(query=normalized_query, results=[], out_of_scope=True)

        semantic = self._semantic_ranking(normalized_query, positions)
        lexical = self._lexical_ranking(normalized_query, positions)
        identifier = self._identifier_bonus(normalized_query, positions)
        semantic_rank = {index: rank for rank, (index, _) in enumerate(semantic, 1)}
        lexical_rank = {index: rank for rank, (index, _) in enumerate(lexical, 1)}
        semantic_raw = dict(semantic)
        lexical_raw = dict(lexical)
        fallback_rank = len(positions) + 1

        results = [
            RetrievalResult(
                chunk=self._chunks[index],
                semantic_score=semantic_raw.get(index, 0.0),
                lexical_score=lexical_raw.get(index, 0.0),
                combined_score=(
                    SEMANTIC_WEIGHT / (RRF_K + semantic_rank.get(index, fallback_rank))
                    + LEXICAL_WEIGHT / (RRF_K + lexical_rank.get(index, fallback_rank))
                    + identifier.get(index, 0.0)
                ),
            )
            for index in positions
        ]
        results.sort(key=lambda item: item.combined_score, reverse=True)
        selected = results[:top_k]
        in_scope = bool(selected) and (bool(identifier) or self._has_evidence(selected))
        return KnowledgeSearchResponse(
            query=normalized_query,
            results=selected if in_scope else [],
            out_of_scope=not in_scope,
        )

    def _has_evidence(self, selected: list[RetrievalResult]) -> bool:
        if self._embedder.is_semantic:
            # Calibrated per embedder on the dev split (see resources/retrieval/thresholds.json).
            return max(item.semantic_score for item in selected) >= self._min_semantic_score
        # The hashing bootstrap has no notion of meaning: require a strong fused rank and
        # lexical overlap.
        if selected[0].combined_score < self._relevance_threshold:
            return False
        return any(item.lexical_score > 0 for item in selected)
