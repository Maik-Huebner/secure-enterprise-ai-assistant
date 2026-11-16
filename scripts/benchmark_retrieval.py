"""Compare embedders on the German retrieval suite (needs a local Ollama for real models).

Usage:
    python scripts/benchmark_retrieval.py [--models bge-m3 qwen3-embedding:0.6b embeddinggemma]

Thresholds are calibrated on the dev split only and reported on the test split. Results are
written to reports/evaluation/retrieval_comparison.json, calibrated thresholds to the packaged
resources/retrieval/thresholds.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.evaluation.retrieval_metrics import (
    calibrate_threshold,
    metrics,
    observe,
)
from secure_enterprise_ai_assistant.rag.embeddings import Embedder, HashingEmbedder, OllamaEmbedder
from secure_enterprise_ai_assistant.rag.ingestion import KnowledgeIngestor
from secure_enterprise_ai_assistant.rag.retrieval import HybridRetriever, searchable_text
from secure_enterprise_ai_assistant.resources import (
    KNOWLEDGE_ROOT,
    RETRIEVAL_SUITE_PATH,
    RETRIEVAL_THRESHOLDS_PATH,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPOSITORY_ROOT / "reports" / "evaluation" / "retrieval_comparison.json"


def _ollama_digests(base_url: str) -> dict[str, str]:
    try:
        tags = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5).json()
    except httpx.HTTPError:
        return {}
    return {model["name"]: model["digest"] for model in tags.get("models", [])}


def _benchmark(embedder: Embedder, suite: dict[str, Any]) -> dict[str, Any]:
    chunks = KnowledgeIngestor(KNOWLEDGE_ROOT).ingest_directory()
    started = time.perf_counter()
    vectors = embedder.encode_documents([searchable_text(chunk) for chunk in chunks])
    index_seconds = time.perf_counter() - started
    # No cut-off while observing; the calibrated threshold is applied afterwards.
    retriever = HybridRetriever(chunks, embedder=embedder, vectors=vectors, min_semantic_score=-1)

    def search(question: str) -> Any:
        return retriever.search(question, top_k=5)

    dev = observe(search, suite["dev"])
    test = observe(search, suite["test"])
    threshold = calibrate_threshold(dev) if embedder.is_semantic else None
    # Sanity check: the production retriever with the calibrated threshold must agree with the
    # post-hoc metric on the test split.
    production = HybridRetriever(
        chunks, embedder=embedder, vectors=vectors, min_semantic_score=threshold
    )
    production_test = observe(lambda question: production.search(question, top_k=5), suite["test"])
    if metrics(production_test)["recall_at_5"] != metrics(test, threshold)["recall_at_5"]:
        raise RuntimeError(f"Benchmark and production disagree for {embedder.name}.")
    misses = [
        {
            "question": item.question,
            "expected": list(item.relevant),
            "top": list(item.ranked_documents[:3]),
        }
        for item in test
        if item.relevant
        and not any(document in item.relevant for document in item.ranked_documents[:5])
    ]
    return {
        "embedder": embedder.name,
        "dimension": int(vectors.shape[1]),
        "chunks": len(chunks),
        "index_build_seconds": round(index_seconds, 2),
        "min_semantic_score": threshold,
        "dev": metrics(dev, threshold),
        "test": metrics(test, threshold),
        "test_misses_before_cutoff": misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models", nargs="*", default=["bge-m3", "qwen3-embedding:0.6b", "embeddinggemma"]
    )
    args = parser.parse_args()
    settings = get_settings()
    suite = json.loads(RETRIEVAL_SUITE_PATH.read_text(encoding="utf-8"))
    digests = _ollama_digests(settings.ollama_base_url)

    embedders: list[Embedder] = [HashingEmbedder()]
    embedders += [OllamaEmbedder(model, base_url=settings.ollama_base_url) for model in args.models]
    results = []
    for embedder in embedders:
        print(f"Messe {embedder.name} …", flush=True)
        results.append(_benchmark(embedder, suite))

    report = {
        "measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "machine": f"{platform.system()} {platform.machine()}",
        "suite": "resources/evaluation/retrieval_suite.json",
        "split_sizes": {
            split: len(items) for split, items in suite.items() if split != "description"
        },
        "model_digests": {
            model: digests.get(model if ":" in model else f"{model}:latest")
            for model in args.models
        },
        "method": (
            "Hybrid FAISS + BM25S + identifier signal, top_k=5. The semantic out-of-scope "
            "threshold is calibrated on dev only; test metrics are reported with that threshold."
        ),
        "results": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    thresholds = json.loads(RETRIEVAL_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    thresholds["min_semantic_score"] = {
        result["embedder"]: result["min_semantic_score"]
        for result in results
        if result["min_semantic_score"] is not None
    }
    thresholds["calibrated_at"] = report["measured_at"]
    RETRIEVAL_THRESHOLDS_PATH.write_text(
        json.dumps(thresholds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for result in results:
        test = result["test"]
        print(
            f"{result['embedder']:<34} test recall@5={test['recall_at_5']:.3f} "
            f"mrr={test['mrr']:.3f} ndcg@5={test['ndcg_at_5']:.3f} "
            f"no-answer={test['no_answer_accuracy']:.3f} "
            f"false-reject={test['false_rejection_rate']:.3f} "
            f"latency={test['median_latency_ms']} ms"
        )


if __name__ == "__main__":
    main()
