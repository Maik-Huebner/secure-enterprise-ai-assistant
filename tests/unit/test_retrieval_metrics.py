"""Tests for retrieval metrics and dev-only threshold calibration."""

from __future__ import annotations

import pytest

from secure_enterprise_ai_assistant.evaluation.retrieval_metrics import (
    Observation,
    calibrate_threshold,
    metrics,
)


def _observation(
    relevant: tuple[str, ...], ranked: tuple[str, ...], score: float, question: str = "Frage"
) -> Observation:
    return Observation(
        question=question,
        relevant=relevant,
        question_type="direct" if relevant else "no_answer",
        ranked_documents=ranked,
        top_semantic_score=score,
        rejected_by_retriever=False,
        identifier_evidence="NB-" in question,
        latency_ms=1.0,
    )


def test_recall_mrr_and_ndcg() -> None:
    observations = [
        _observation(("A",), ("A", "B"), 0.9),
        _observation(("B",), ("A", "B"), 0.8),
        _observation(("C",), ("A", "B"), 0.7),
    ]

    result = metrics(observations)

    assert result["recall_at_5"] == pytest.approx(2 / 3, abs=1e-4)
    assert result["mrr"] == pytest.approx((1 + 0.5 + 0) / 3, abs=1e-4)
    assert 0 < result["ndcg_at_5"] < 1


def test_threshold_trades_false_rejections_against_no_answer_accuracy() -> None:
    observations = [
        _observation(("A",), ("A",), 0.80),
        _observation(("B",), ("B",), 0.70),
        _observation((), ("A",), 0.40),
        _observation((), ("B",), 0.30),
    ]

    threshold = calibrate_threshold(observations)
    result = metrics(observations, threshold)

    assert 0.40 < threshold < 0.70
    assert result["recall_at_5"] == 1.0
    assert result["no_answer_accuracy"] == 1.0
    assert result["false_rejection_rate"] == 0.0


def test_identifier_questions_are_never_cut_by_the_semantic_threshold() -> None:
    observation = _observation(("A",), ("A",), 0.1, question="Was steht in NB-AAA-001?")

    assert metrics([observation], threshold=0.9)["recall_at_5"] == 1.0
