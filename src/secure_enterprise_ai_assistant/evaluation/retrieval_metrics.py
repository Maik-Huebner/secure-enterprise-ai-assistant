"""Retrieval metrics on the German retrieval suite, with dev-only threshold calibration."""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.rag.retrieval import DOCUMENT_ID_PATTERN

SearchFunction = Callable[[str], KnowledgeSearchResponse]


@dataclass(frozen=True)
class Observation:
    """One question with its ranked documents before any out-of-scope cut-off."""

    question: str
    relevant: tuple[str, ...]
    question_type: str
    ranked_documents: tuple[str, ...]
    top_semantic_score: float
    rejected_by_retriever: bool
    identifier_evidence: bool
    latency_ms: float


def _unique(documents: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for document in documents:
        if document not in seen:
            seen.append(document)
    return seen


def observe(search: SearchFunction, items: Sequence[dict[str, Any]]) -> list[Observation]:
    """Run every question once and record ranking, top semantic score, and latency."""
    observations = []
    for item in items:
        started = time.perf_counter()
        response = search(item["question"])
        latency = (time.perf_counter() - started) * 1000
        observations.append(
            Observation(
                question=item["question"],
                relevant=tuple(item["relevant"]),
                question_type=item["type"],
                ranked_documents=tuple(
                    _unique([result.chunk.document_id for result in response.results])
                ),
                top_semantic_score=max(
                    (result.semantic_score for result in response.results), default=0.0
                ),
                rejected_by_retriever=response.out_of_scope,
                # Mirrors HybridRetriever: an explicit document ID always counts as evidence.
                identifier_evidence=bool(DOCUMENT_ID_PATTERN.search(item["question"])),
                latency_ms=latency,
            )
        )
    return observations


def _rejected(observation: Observation, threshold: float | None) -> bool:
    if threshold is None or observation.identifier_evidence:
        return observation.rejected_by_retriever
    return observation.rejected_by_retriever or observation.top_semantic_score < threshold


def metrics(observations: Sequence[Observation], threshold: float | None = None) -> dict[str, Any]:
    """Compute retrieval metrics. ``threshold`` applies a semantic out-of-scope cut-off."""
    answerable = [item for item in observations if item.relevant]
    unanswerable = [item for item in observations if not item.relevant]
    recall_hits = 0
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    false_rejections = 0
    per_type: dict[str, list[int]] = {}
    for item in answerable:
        rejected = _rejected(item, threshold)
        ranked = [] if rejected else list(item.ranked_documents[:5])
        false_rejections += rejected
        hit = any(document in item.relevant for document in ranked)
        recall_hits += hit
        per_type.setdefault(item.question_type, []).append(int(hit))
        first = next(
            (rank for rank, document in enumerate(ranked, 1) if document in item.relevant), None
        )
        reciprocal_ranks.append(1 / first if first else 0.0)
        dcg = sum(
            1 / math.log2(rank + 1)
            for rank, document in enumerate(ranked, 1)
            if document in item.relevant
        )
        ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(item.relevant), 5) + 1))
        ndcgs.append(dcg / ideal if ideal else 0.0)
    no_answer_correct = sum(_rejected(item, threshold) for item in unanswerable)

    def ratio(value: float, total: int) -> float:
        return round(value / total, 4) if total else 0.0

    return {
        "answerable_questions": len(answerable),
        "no_answer_questions": len(unanswerable),
        "recall_at_5": ratio(recall_hits, len(answerable)),
        "mrr": ratio(sum(reciprocal_ranks), len(answerable)),
        "ndcg_at_5": ratio(sum(ndcgs), len(answerable)),
        "no_answer_accuracy": ratio(no_answer_correct, len(unanswerable)),
        "false_rejection_rate": ratio(false_rejections, len(answerable)),
        "recall_at_5_by_type": {
            name: ratio(sum(values), len(values)) for name, values in sorted(per_type.items())
        },
        "median_latency_ms": round(statistics.median(item.latency_ms for item in observations), 1),
    }


def calibrate_threshold(observations: Sequence[Observation]) -> float:
    """Pick the semantic cut-off that maximizes (recall@5 + no-answer accuracy) / 2 on dev.

    Ties are resolved by taking the middle of the longest contiguous run of best candidates,
    which keeps the margin to neighbouring scores as large as possible.
    """
    scores = sorted({round(item.top_semantic_score, 4) for item in observations})
    candidates = (
        [scores[0] - 0.01]
        + [(low + high) / 2 for low, high in zip(scores, scores[1:], strict=False)]
        + [scores[-1] + 0.01]
    )

    def objective(threshold: float) -> float:
        result = metrics(observations, threshold)
        return float(result["recall_at_5"] + result["no_answer_accuracy"]) / 2

    values = [objective(candidate) for candidate in candidates]
    best = max(values)
    runs: list[list[float]] = []
    for candidate, value in zip(candidates, values, strict=True):
        if value == best:
            if runs and runs[-1][-1] == candidates[candidates.index(candidate) - 1]:
                runs[-1].append(candidate)
            else:
                runs.append([candidate])
    longest = max(runs, key=len)
    return round((longest[0] + longest[-1]) / 2, 4)
