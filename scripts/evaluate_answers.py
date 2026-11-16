"""Measure answer quality of the real stack (LangGraph + MCP + local Ollama model).

Usage (needs Ollama with the configured models and a built index):
    python scripts/evaluate_answers.py

Writes reports/evaluation/answer_quality.json. Nothing here runs in CI: it needs the local
model. A random JWT secret is generated per run; the evaluation acts as an admin principal.
The ``manual_review`` block of the report is added by hand afterwards; earlier runs are kept
as answer_quality_run<N>.json.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_ollama import ChatOllama  # noqa: E402

from secure_enterprise_ai_assistant.core.settings import get_settings  # noqa: E402
from secure_enterprise_ai_assistant.evaluation.answer_quality import (  # noqa: E402
    citation_check,
    declined,
    fact_hits,
    ratio,
)
from secure_enterprise_ai_assistant.graph.assistant import AssistantService  # noqa: E402
from secure_enterprise_ai_assistant.graph.evidence_text import (  # noqa: E402
    evidence_document_ids,
    prompt_context,
)
from secure_enterprise_ai_assistant.graph.verification import (  # noqa: E402
    DOCUMENT_ID,
    verify_answer,
)
from secure_enterprise_ai_assistant.mcp.client import McpEvidenceClient  # noqa: E402
from secure_enterprise_ai_assistant.mcp.server import token_service_from_settings  # noqa: E402
from secure_enterprise_ai_assistant.resources import RESOURCE_ROOT  # noqa: E402
from secure_enterprise_ai_assistant.security import Principal  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "evaluation" / "answer_quality.json"
SUITE_PATH = RESOURCE_ROOT / "evaluation" / "answer_suite.json"

JUDGE_SYSTEM = (
    "Du prüfst Antworten eines Bank-Assistenten. Entscheide, ob JEDE inhaltliche Aussage der "
    "ANTWORT durch die NACHWEISE gestützt ist. Formulierungen dürfen abweichen, Fakten nicht. "
    'Antworte ausschließlich mit JSON: {"belegt": true oder false, "unbelegt": ["..."]}'
)
LLM_ONLY_SYSTEM = (
    "Du bist der Assistent der NovaBank. Beantworte die Frage knapp auf Deutsch zu den "
    "internen Kreditrichtlinien der NovaBank."
)


class CapturingCollector:
    """Wraps the real MCP client and keeps the evidence of the last run for scoring."""

    last: dict[str, Any] = {}

    def __init__(self, access_token: str | None) -> None:
        self._inner = McpEvidenceClient(access_token)

    def collect(self, route: Any, query: str) -> dict[str, Any]:
        evidence = self._inner.collect(route, query)
        CapturingCollector.last = evidence
        return evidence


def _judge(chat: ChatOllama, evidence: dict[str, Any], answer: str) -> dict[str, Any]:
    user = f"NACHWEISE:\n{prompt_context(evidence)}\n\nANTWORT:\n{answer}"
    raw = str(
        chat.invoke([SystemMessage(content=JUDGE_SYSTEM), HumanMessage(content=user)]).content
    )
    try:
        verdict = json.loads(raw)
        return {
            "supported": bool(verdict.get("belegt")),
            "unsupported": verdict.get("unbelegt", []),
        }
    except json.JSONDecodeError:
        return {"supported": None, "unsupported": [], "raw": raw[:200]}


def main() -> None:
    settings = get_settings()
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))["items"]
    principal = Principal.system()
    verifier = token_service_from_settings()
    assert verifier is not None
    token = verifier.issue(principal)[0]
    service = AssistantService(collector=CapturingCollector, settings=settings)
    judge = ChatOllama(
        model=settings.ollama_fast_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        format="json",
        reasoning=False,
        seed=settings.llm_seed,
    )
    baseline = ChatOllama(
        model=settings.ollama_fast_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
        reasoning=False,
        seed=settings.llm_seed,
        num_predict=settings.llm_max_tokens,
    )

    rows: list[dict[str, Any]] = []
    for item in suite:
        print(f"→ {item['question']}", flush=True)
        CapturingCollector.last = {}
        started = time.perf_counter()
        result = service.run(item["question"], principal, token)
        seconds = round(time.perf_counter() - started, 1)
        evidence = CapturingCollector.last
        hits = fact_hits(result.answer, item["facts"])
        row: dict[str, Any] = {
            "question": item["question"],
            "kind": item["kind"],
            "execution_mode": result.execution_mode,
            "attempts": sum(
                1 for event in result.trace if event.event in {"model_selected", "answer_retry"}
            ),
            "seconds": seconds,
            "answer": result.answer,
        }
        if item["kind"] == "no_answer":
            row["correct"] = result.execution_mode == "no_answer" or declined(result.answer)
        else:
            row["fact_hits"] = hits
            row["correct"] = all(hits)
            row["fact_recall"] = round(sum(hits) / len(hits), 4)
            row["remaining_issues"] = verify_answer(result.answer, evidence, result.route.case_id)
            if item["expected_documents"]:
                grounded_ids = evidence_document_ids(evidence) | set(
                    DOCUMENT_ID.findall(prompt_context(evidence))
                )
                row["citations"] = citation_check(
                    result.answer, grounded_ids, item["expected_documents"]
                )
            if result.execution_mode == "llm_grounded":
                row["judge"] = _judge(judge, evidence, result.answer)
        if item["kind"] == "knowledge":
            raw = str(
                baseline.invoke(
                    [SystemMessage(content=LLM_ONLY_SYSTEM), HumanMessage(content=item["question"])]
                ).content
            )
            row["llm_only"] = {"answer": raw, "correct": all(fact_hits(raw, item["facts"]))}
        rows.append(row)
        print(f"   {row['execution_mode']}, korrekt={row['correct']}, {seconds} s", flush=True)

    answerable = [row for row in rows if row["kind"] != "no_answer"]
    knowledge = [row for row in rows if row["kind"] == "knowledge"]
    grounded = [row for row in rows if row["execution_mode"] == "llm_grounded"]
    summary = {
        "answer_correct_rate": ratio([row["correct"] for row in answerable]),
        "fact_recall_mean": round(statistics.mean(row["fact_recall"] for row in answerable), 4),
        "no_answer_correct_rate": ratio(
            [row["correct"] for row in rows if row["kind"] == "no_answer"]
        ),
        "citation_grounded_rate": ratio(
            [row["citations"]["only_grounded_cited"] for row in answerable if "citations" in row]
        ),
        "citation_expected_rate": ratio(
            [row["citations"]["expected_cited"] for row in answerable if "citations" in row]
        ),
        "final_answers_with_open_issues": sum(1 for row in answerable if row["remaining_issues"]),
        "llm_grounded_rate": ratio([row["execution_mode"] == "llm_grounded" for row in answerable]),
        "verified_fallback_rate": ratio(
            [row["execution_mode"] == "verified_fallback" for row in answerable]
        ),
        "retry_rate": ratio([row["attempts"] > 1 for row in answerable]),
        "judge_supported_rate": ratio([row["judge"]["supported"] for row in grounded]),
        "knowledge_correct_rag": ratio([row["correct"] for row in knowledge]),
        "knowledge_correct_llm_only": ratio([row["llm_only"]["correct"] for row in knowledge]),
        "median_seconds": statistics.median(row["seconds"] for row in rows),
    }
    report = {
        "measured_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "machine": f"{platform.system()} {platform.machine()}",
        "model": settings.ollama_fast_model,
        "embedding_model": settings.embedding_model,
        "judge": f"{settings.ollama_fast_model} (same model, temperature 0, JSON mode)",
        "counts": {"items": len(rows), "answerable": len(answerable), "knowledge": len(knowledge)},
        "summary": summary,
        "notes": (
            "Facts are checked by substring match on accepted spellings. The faithfulness judge "
            "is the same 9B model that writes the answers and is therefore a weak, biased judge; "
            "see manual_review for a spot check. LLM-only means the same model without evidence."
        ),
        "items": rows,
        # Filled in by hand after reading every grounded answer (see docs/lernnotizen).
        "manual_review": None,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
