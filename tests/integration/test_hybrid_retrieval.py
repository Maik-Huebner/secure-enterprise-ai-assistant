"""Offline integration tests for hybrid retrieval and source attribution."""

from secure_enterprise_ai_assistant.development.knowledge_base import write_knowledge_base
from secure_enterprise_ai_assistant.rag.service import KnowledgeService


def test_required_documents_query_returns_policy_source(tmp_path) -> None:
    write_knowledge_base(tmp_path)
    response = KnowledgeService.from_directory(tmp_path).search(
        "Welche Pflichtnachweise braucht eine Verbraucherkreditakte?",
        top_k=5,
    )

    assert response.out_of_scope is False
    assert any(item.chunk.document_id == "NB-DOC-001" for item in response.results)
    assert all(item.chunk.section for item in response.results)


def test_metadata_filter_is_enforced(tmp_path) -> None:
    write_knowledge_base(tmp_path)
    response = KnowledgeService.from_directory(tmp_path).search(
        "Wo liegt die harte Grenze der Schuldendienstquote?",
        metadata_filter={"document_id": "NB-RSK-001"},
    )

    assert response.results
    assert {item.chunk.document_id for item in response.results} == {"NB-RSK-001"}


def test_unrelated_query_is_out_of_scope(tmp_path) -> None:
    write_knowledge_base(tmp_path)
    response = KnowledgeService.from_directory(tmp_path).search(
        "Vulkanische Petrologie, Zeolithe und Mantelkonvektion",
    )

    assert response.out_of_scope is True
    assert response.results == []
