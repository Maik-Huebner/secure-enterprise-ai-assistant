"""Compare keyword, semantic, and hybrid routing on the routing suite (needs local Ollama).

Usage:
    python scripts/benchmark_routing.py [--model qwen3-embedding:0.6b]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.flows.router import IntentRouter
from secure_enterprise_ai_assistant.rag.embeddings import OllamaEmbedder
from secure_enterprise_ai_assistant.resources import ROUTING_SUITE_PATH

REPORT_PATH = (
    Path(__file__).resolve().parents[1] / "reports" / "evaluation" / "routing_comparison.json"
)


def _evaluate(router: IntentRouter, items: list[list[str]]) -> dict[str, Any]:
    started = time.perf_counter()
    wrong = []
    for query, expected in items:
        actual = router.classify(query).intent.value
        if actual != expected:
            wrong.append({"query": query, "expected": expected, "actual": actual})
    elapsed = (time.perf_counter() - started) * 1000 / len(items)
    return {
        "accuracy": round((len(items) - len(wrong)) / len(items), 4),
        "correct": len(items) - len(wrong),
        "total": len(items),
        "mean_latency_ms": round(elapsed, 1),
        "errors": wrong,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=get_settings().embedding_model)
    args = parser.parse_args()
    suite = json.loads(ROUTING_SUITE_PATH.read_text(encoding="utf-8"))
    embedder = OllamaEmbedder(args.model, base_url=get_settings().ollama_base_url)
    routers = {
        "keyword": IntentRouter(),
        "semantic": IntentRouter(embedder, "semantic"),
        "hybrid": IntentRouter(embedder, "hybrid"),
    }
    results = {
        name: {split: _evaluate(router, suite[split]) for split in ("dev", "test")}
        for name, router in routers.items()
    }
    report = {
        "measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "embedder": embedder.name,
        "note": (
            "Keyword stems come from the intent examples and the dev split only. The test split "
            "was written by the same author before the rules, so it is not a blind benchmark."
        ),
        "results": results,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for name, result in results.items():
        print(
            f"{name:<9} dev {result['dev']['correct']}/{result['dev']['total']}  "
            f"test {result['test']['correct']}/{result['test']['total']}  "
            f"{result['test']['mean_latency_ms']} ms"
        )
        for error in result["test"]["errors"]:
            print("    ", error)


if __name__ == "__main__":
    main()
