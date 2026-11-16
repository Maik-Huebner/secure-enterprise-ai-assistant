"""Tests for embeddings, the persistent index, pre-ranking filters and identifier ranking."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import httpx
import numpy as np
import pytest

from secure_enterprise_ai_assistant.rag import cli
from secure_enterprise_ai_assistant.rag.embeddings import (
    EmbeddingUnavailableError,
    HashingEmbedder,
    OllamaEmbedder,
    prompt_format_for,
)
from secure_enterprise_ai_assistant.rag.index_store import (
    expected_manifest,
    index_directory,
    load_index,
    read_manifest,
)
from secure_enterprise_ai_assistant.rag.ingestion import KnowledgeIngestor
from secure_enterprise_ai_assistant.rag.retrieval import HybridRetriever, section_number
from secure_enterprise_ai_assistant.rag.service import KnowledgeService, build_index
from secure_enterprise_ai_assistant.resources import KNOWLEDGE_ROOT


class FakeSemanticEmbedder:
    """Hashing vectors that pretend to be semantic, to exercise the semantic code paths."""

    is_semantic = True

    def __init__(self) -> None:
        self._inner = HashingEmbedder()
        self.document_calls = 0

    @property
    def name(self) -> str:
        return "fake-semantic"

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        self.document_calls += 1
        return self._inner.encode_documents(texts)

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._inner.encode_queries(texts)


@pytest.fixture(scope="module")
def chunks():
    return KnowledgeIngestor(KNOWLEDGE_ROOT).ingest_directory()


def test_metadata_header_is_not_indexed_as_a_search_hit(chunks) -> None:
    assert all(chunk.section != "Dokumentmetadaten" for chunk in chunks)
    assert all(chunk.version != "unbekannt" for chunk in chunks)


def test_prompt_formats_follow_model_cards() -> None:
    assert prompt_format_for("qwen3-embedding:0.6b").query.startswith("Instruct:")
    assert prompt_format_for("embeddinggemma").document.startswith("title: none")
    assert prompt_format_for("bge-m3").query == "{text}"


def test_ollama_embedder_reports_unreachable_server_in_german(monkeypatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", refuse)

    with pytest.raises(EmbeddingUnavailableError, match="ollama pull qwen3-embedding:0.6b"):
        OllamaEmbedder("qwen3-embedding:0.6b").encode_queries(["Test"])


def test_ollama_embedder_batches_and_normalizes(monkeypatch) -> None:
    calls: list[list[str]] = []

    class Response:
        def __init__(self, inputs: list[str]) -> None:
            self._inputs = inputs

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[list[float]]]:
            return {"embeddings": [[3.0, 4.0] for _ in self._inputs]}

    def fake_post(_url: str, json: dict[str, object], timeout: float) -> Response:
        del timeout
        inputs = list(json["input"])  # type: ignore[call-overload]
        calls.append(inputs)
        return Response(inputs)

    monkeypatch.setattr(httpx, "post", fake_post)
    vectors = OllamaEmbedder("bge-m3", batch_size=2).encode_documents(["a", "b", "c"])

    assert [len(batch) for batch in calls] == [2, 1]
    assert np.allclose(vectors[0], [0.6, 0.8])


def test_persistent_index_is_reused_and_rebuilt_when_corpus_changes(tmp_path: Path) -> None:
    embedder = FakeSemanticEmbedder()
    KnowledgeService.from_directory(embedder=embedder, index_root=tmp_path)
    assert embedder.document_calls == 1
    manifest = read_manifest(index_directory(tmp_path, embedder.name))
    assert manifest is not None and manifest.embedder == "fake-semantic"

    KnowledgeService.from_directory(embedder=embedder, index_root=tmp_path)
    assert embedder.document_calls == 1, "a matching index must be loaded, not rebuilt"

    changed_root = tmp_path / "kb"
    changed_root.mkdir()
    for path in KNOWLEDGE_ROOT.glob("*.md"):
        (changed_root / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    first = sorted(changed_root.glob("*.md"))[0]
    first.write_text(first.read_text(encoding="utf-8") + "\n## 99 Neu\nGeänderter Text.\n")
    KnowledgeService.from_directory(changed_root, embedder=embedder, index_root=tmp_path)
    assert embedder.document_calls == 2, "a changed corpus must trigger a rebuild"


def test_stale_manifest_is_not_loaded(tmp_path: Path, chunks) -> None:
    embedder = FakeSemanticEmbedder()
    build_index(chunks, embedder, tmp_path)
    directory = index_directory(tmp_path, embedder.name)

    assert load_index(directory, expected_manifest(chunks, embedder.name, 0)) is not None
    assert load_index(directory, expected_manifest(chunks[:-1], embedder.name, 0)) is None
    assert load_index(directory, expected_manifest(chunks, "other-model", 0)) is None


def test_filters_are_applied_before_ranking(chunks) -> None:
    retriever = HybridRetriever(chunks)
    query = "Welche Risikoklassen sind zulässig?"

    allowed = retriever.search(query, allowed_document_ids={"NB-RSK-002", "NB-DOC-001"})
    hidden_only = retriever.search(query, allowed_document_ids={"NB-FEE-001"})
    nothing = retriever.search(query, allowed_document_ids=set())

    assert {item.chunk.document_id for item in allowed.results} <= {"NB-RSK-002", "NB-DOC-001"}
    assert all(item.chunk.document_id == "NB-FEE-001" for item in hidden_only.results)
    assert nothing.out_of_scope is True and nothing.results == []


def test_rank_positions_do_not_depend_on_hidden_documents(chunks) -> None:
    retriever = HybridRetriever(chunks, embedder=FakeSemanticEmbedder(), min_semantic_score=-1)
    query = "Welche Risikoklassen sind zulässig?"
    allowed = {"NB-RSK-002", "NB-RSK-001"}

    filtered = retriever.search(query, allowed_document_ids=allowed)
    subset = HybridRetriever(
        [chunk for chunk in chunks if chunk.document_id in allowed],
        embedder=FakeSemanticEmbedder(),
        min_semantic_score=-1,
    ).search(query)

    assert [item.chunk.chunk_id for item in filtered.results] == [
        item.chunk.chunk_id for item in subset.results
    ]
    assert [item.semantic_score for item in filtered.results] == pytest.approx(
        [item.semantic_score for item in subset.results]
    )


def test_document_and_section_identifiers_rank_first(chunks) -> None:
    response = HybridRetriever(chunks).search("Was steht in NB-RSK-001 Abschnitt 7.4?")

    assert response.out_of_scope is False
    assert response.results[0].chunk.document_id == "NB-RSK-001"
    assert section_number(response.results[0].chunk.section) == "7.4"


def test_semantic_threshold_rejects_weak_matches(chunks) -> None:
    strict = HybridRetriever(chunks, embedder=FakeSemanticEmbedder(), min_semantic_score=0.99)
    lenient = HybridRetriever(chunks, embedder=FakeSemanticEmbedder(), min_semantic_score=-1)

    assert strict.search("Gibt es eine Bearbeitungsgebühr?").out_of_scope is True
    assert lenient.search("Gibt es eine Bearbeitungsgebühr?").out_of_scope is False


def test_index_cli_reports_status_and_rebuilds(tmp_path: Path, monkeypatch, capsys) -> None:
    from secure_enterprise_ai_assistant.core.settings import Settings

    settings = Settings(embedding_backend="hashing", index_dir=tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "build_embedder", lambda _settings: FakeSemanticEmbedder())

    assert cli.main(["status"]) == 1
    assert cli.main(["rebuild"]) == 0
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "Index neu aufgebaut" in output
    assert '"aktuell": true' in output
