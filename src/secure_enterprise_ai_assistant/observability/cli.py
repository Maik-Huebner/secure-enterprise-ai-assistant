"""``novabank-langfuse``: connect the assistant to a (self-hosted) Langfuse project.

Commands:
  check       test the keys against the Langfuse server
  setup       register the local answer model with the configured price per token
  datasets    upload the answer and retrieval suites as Langfuse datasets
  experiment  run the answer suite through the real workflow as a Langfuse experiment
              (needs Ollama; every item becomes a trace with scores)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from typing import TYPE_CHECKING, Any

from secure_enterprise_ai_assistant import __version__
from secure_enterprise_ai_assistant.core.settings import Settings, get_settings
from secure_enterprise_ai_assistant.evaluation.answer_quality import declined, fact_hits
from secure_enterprise_ai_assistant.observability.tracing import Tracing, build_tracing
from secure_enterprise_ai_assistant.resources import RESOURCE_ROOT

if TYPE_CHECKING:
    from langfuse import Langfuse

ANSWER_DATASET = "novabank-answer-suite"
RETRIEVAL_DATASET = "novabank-retrieval-test"


def _client(settings: Settings) -> tuple[Tracing, Langfuse]:
    tracing = build_tracing(settings.model_copy(update={"langfuse_enabled": True}))
    if tracing.client is None:
        sys.exit("LANGFUSE_PUBLIC_KEY und LANGFUSE_SECRET_KEY fehlen (siehe README, Langfuse).")
    return tracing, tracing.client


def check(settings: Settings) -> None:
    _, client = _client(settings)
    ok = client.auth_check()
    status = "verbunden" if ok else "Anmeldung fehlgeschlagen"
    print(f"Langfuse {settings.langfuse_base_url}: {status}")
    if not ok:
        sys.exit(1)


def setup(settings: Settings) -> None:
    """Create a model definition so Langfuse can compute cost from token usage."""
    from langfuse.api.commons.types import PricingTierInput

    _, client = _client(settings)
    model = settings.ollama_fast_model
    prices = {
        "input": settings.llm_price_input_per_million_tokens / 1_000_000,
        "output": settings.llm_price_output_per_million_tokens / 1_000_000,
    }
    # Idempotent: replace our own earlier definition instead of stacking new ones.
    page = 1
    while True:
        listing = client.api.models.list(page=page, limit=100)
        for existing in listing.data:
            if existing.model_name == model and not existing.is_langfuse_managed:
                client.api.models.delete(existing.id)
        if page >= listing.meta.total_pages:
            break
        page += 1
    client.api.models.create(
        model_name=model,
        match_pattern=f"(?i)^{re.escape(model)}$",
        unit="TOKENS",
        pricing_tiers=[
            PricingTierInput(
                name="Lokal (Annahme)", is_default=True, priority=0, conditions=[], prices=prices
            )
        ],
    )
    print(
        f"Modell {model} angelegt: {settings.llm_price_input_per_million_tokens} / "
        f"{settings.llm_price_output_per_million_tokens} pro 1 Mio. Eingabe-/Ausgabe-Token "
        "(Langfuse zeigt USD an; lokal entstehen keine API-Kosten)."
    )


def _suite(name: str, key: str = "items") -> list[dict[str, Any]]:
    data = json.loads((RESOURCE_ROOT / "evaluation" / name).read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = data[key]
    return items


def datasets(settings: Settings) -> None:
    """Upload the versioned suites; item IDs are stable, so repeated uploads update in place."""
    _, client = _client(settings)
    client.create_dataset(
        name=ANSWER_DATASET,
        description="17 deutsche Fragen an den Assistenten (fiktive NovaBank-Daten).",
        metadata={"source": "resources/evaluation/answer_suite.json", "version": __version__},
    )
    for index, item in enumerate(_suite("answer_suite.json")):
        client.create_dataset_item(
            dataset_name=ANSWER_DATASET,
            id=f"answer-{index:02d}",
            input={"question": item["question"]},
            expected_output={
                "facts": item["facts"],
                "expected_documents": item.get("expected_documents", []),
            },
            metadata={"kind": item["kind"]},
        )
    retrieval = _suite("retrieval_suite.json", "test")
    client.create_dataset(
        name=RETRIEVAL_DATASET,
        description="Test-Split der Suchfragen (nicht zum Abstimmen verwendet).",
        metadata={"source": "resources/evaluation/retrieval_suite.json"},
    )
    for index, item in enumerate(retrieval):
        client.create_dataset_item(
            dataset_name=RETRIEVAL_DATASET,
            id=f"retrieval-{index:02d}",
            input={"question": item["question"]},
            expected_output={"relevant": item.get("relevant", [])},
            metadata={"type": item.get("type")},
        )
    client.flush()
    print(f"Datensätze hochgeladen: {ANSWER_DATASET}, {RETRIEVAL_DATASET} ({len(retrieval)}).")


def experiment(settings: Settings, run_name: str | None) -> None:
    """Run every answer-suite item through the real graph; scores are attached per item."""
    from langfuse.experiment import Evaluation

    from secure_enterprise_ai_assistant.graph.assistant import AssistantService
    from secure_enterprise_ai_assistant.security import Principal
    from secure_enterprise_ai_assistant.security.tokens import mcp_token_service

    tracing, client = _client(settings)
    tokens = mcp_token_service(settings)
    if tokens is None:
        sys.exit("JWT_SECRET fehlt.")
    principal = Principal.system()
    service = AssistantService(settings=settings, tracing=tracing)
    dataset = client.get_dataset(ANSWER_DATASET)

    async def task(*, item: Any, **_: Any) -> dict[str, Any]:
        # The experiment runner owns an event loop; the MCP client starts its own, so the
        # synchronous workflow runs in a worker thread (context variables, and with them the
        # trace context, are copied into it).
        result = await asyncio.to_thread(
            service.run, item.input["question"], principal, tokens.issue(principal)[0]
        )
        return {"answer": result.answer, "execution_mode": result.execution_mode}

    def facts(*, output: dict[str, Any], expected_output: dict[str, Any], **_: Any) -> Evaluation:
        if not expected_output["facts"]:
            return Evaluation(name="facts_correct", value=float(declined(output["answer"])))
        hits = fact_hits(output["answer"], expected_output["facts"])
        return Evaluation(name="facts_correct", value=float(all(hits)), comment=str(hits))

    def mode(*, output: dict[str, Any], **_: Any) -> Evaluation:
        return Evaluation(
            name="execution_mode", value=str(output["execution_mode"]), data_type="CATEGORICAL"
        )

    result = dataset.run_experiment(
        name="novabank-answer-quality",
        run_name=run_name,
        description=f"v{__version__}, {settings.ollama_fast_model}, {settings.embedding_model}",
        task=task,
        evaluators=[facts, mode],
        max_concurrency=1,  # one local model; parallel calls would only queue in Ollama
    )
    service.close()
    tracing.flush()
    print(result.format())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novabank-langfuse", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("setup")
    commands.add_parser("datasets")
    run = commands.add_parser("experiment")
    run.add_argument("--run-name", default=None)
    arguments = parser.parse_args(argv)
    settings = get_settings()
    if arguments.command == "check":
        check(settings)
    elif arguments.command == "setup":
        setup(settings)
    elif arguments.command == "datasets":
        datasets(settings)
    else:
        experiment(settings, arguments.run_name)


if __name__ == "__main__":
    main()
