"""Structured models for knowledge ingestion and retrieval."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from secure_enterprise_ai_assistant.models.domain import DomainModel


class KnowledgeChunk(DomainModel):
    """One provenance-preserving section chunk."""

    chunk_id: str
    document_id: str
    title: str
    version: str
    effective_date: str
    owner: str
    classification: Literal["intern", "vertraulich"] = "vertraulich"
    section: str
    page: int | None = Field(default=None, ge=1)
    content: str = Field(min_length=1)
    security_flags: list[str] = Field(default_factory=list)


class RetrievalResult(DomainModel):
    """One ranked retrieval result with transparent component scores."""

    chunk: KnowledgeChunk
    semantic_score: float
    lexical_score: float
    combined_score: float


class KnowledgeSearchResponse(DomainModel):
    """Safe structured result returned to MCP clients and agents."""

    query: str
    results: list[RetrievalResult]
    out_of_scope: bool
