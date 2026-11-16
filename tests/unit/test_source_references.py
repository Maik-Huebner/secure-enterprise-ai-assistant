"""Every compliance rule must cite a document section that really exists."""

import json

import pytest

from secure_enterprise_ai_assistant.rag.ingestion import KnowledgeIngestor
from secure_enterprise_ai_assistant.resources import KNOWLEDGE_ROOT, RULES_PATH

RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))["rules"]
CHUNKS = KnowledgeIngestor(KNOWLEDGE_ROOT).ingest_directory()
SECTIONS = {(chunk.document_id, chunk.section) for chunk in CHUNKS}
TITLES = {chunk.document_id: chunk.title for chunk in CHUNKS}


@pytest.mark.parametrize("rule", RULES, ids=[rule["rule_id"] for rule in RULES])
def test_rule_cites_existing_document_and_section(rule: dict[str, str]) -> None:
    document_id, _, title = rule["source_document"].partition(" — ")

    assert document_id in TITLES, f"unknown document {document_id}"
    assert title == TITLES[document_id]
    assert (document_id, rule["source_section"]) in SECTIONS


def test_policy_cross_references_point_to_existing_documents() -> None:
    referenced = {
        token.rstrip(".,;:)")
        for chunk in CHUNKS
        for token in chunk.content.split()
        if token.startswith("NB-")
    }

    assert referenced <= set(TITLES)
