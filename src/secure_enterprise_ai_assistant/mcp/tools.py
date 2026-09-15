"""Business facade used exclusively by the allowlisted MCP tools."""

from __future__ import annotations

import re

from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.guardrails import validate_user_query
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.models.tools import (
    ComplianceCheckResult,
    CustomerCaseResult,
    FinancialAnalysisResult,
)
from secure_enterprise_ai_assistant.rag import KnowledgeService
from secure_enterprise_ai_assistant.rag.retrieval import SentenceTransformerEmbedder
from secure_enterprise_ai_assistant.services import (
    ComplianceService,
    CustomerCaseRepository,
    FinancialAnalysisService,
)

CASE_ID_PATTERN = re.compile(r"^CASE-\d{5}$")
ALLOWED_METADATA_FILTERS = {"document_id", "owner", "version"}


class MCPToolService:
    """Validated application boundary behind the real MCP server."""

    def __init__(
        self,
        repository: CustomerCaseRepository,
        financial_service: FinancialAnalysisService,
        compliance_service: ComplianceService,
        knowledge_service: KnowledgeService,
    ) -> None:
        self.repository = repository
        self.financial_service = financial_service
        self.compliance_service = compliance_service
        self.knowledge_service = knowledge_service

    @classmethod
    def build_default(cls) -> MCPToolService:
        """Build the local-first tool boundary from repository-owned data."""
        settings = get_settings()
        embedder = (
            SentenceTransformerEmbedder(settings.embedding_model)
            if settings.embedding_model
            else None
        )
        return cls(
            repository=CustomerCaseRepository.from_json(),
            financial_service=FinancialAnalysisService(),
            compliance_service=ComplianceService.from_json(),
            knowledge_service=KnowledgeService.from_directory(embedder=embedder),
        )

    @staticmethod
    def _case_id(case_id: str) -> str:
        normalized = case_id.strip().upper()
        if not CASE_ID_PATTERN.fullmatch(normalized):
            raise ValueError("case_id must match CASE- followed by five digits.")
        return normalized

    def get_customer_case(self, case_id: str) -> CustomerCaseResult:
        """Load a validated synthetic customer case by case ID."""
        return CustomerCaseResult(case=self.repository.get_case(self._case_id(case_id)))

    def analyze_financial_case(self, case_id: str) -> FinancialAnalysisResult:
        """Calculate precise annuity and debt-to-income metrics for a case."""
        normalized = self._case_id(case_id)
        case = self.repository.get_case(normalized)
        return FinancialAnalysisResult(
            case_id=normalized,
            metrics=self.financial_service.analyze(case),
        )

    def check_compliance(self, case_id: str) -> ComplianceCheckResult:
        """Evaluate every machine-readable NovaBank rule for a case."""
        normalized = self._case_id(case_id)
        case = self.repository.get_case(normalized)
        return ComplianceCheckResult(
            case_id=normalized,
            findings=list(self.compliance_service.check(case)),
        )

    def search_internal_knowledge(
        self,
        question: str,
        top_k: int = 5,
        document_id: str | None = None,
        owner: str | None = None,
        version: str | None = None,
    ) -> KnowledgeSearchResponse:
        """Search synthetic internal policies and return attributable chunks."""
        normalized_question = validate_user_query(question)
        if len(normalized_question) > 1000:
            raise ValueError("question must contain at most 1000 characters.")
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be between 1 and 10.")
        supplied_filters = {
            "document_id": document_id,
            "owner": owner,
            "version": version,
        }
        metadata_filter = {
            key: value.strip()
            for key, value in supplied_filters.items()
            if value is not None and value.strip()
        }
        if not metadata_filter.keys() <= ALLOWED_METADATA_FILTERS:
            raise ValueError("Unsupported metadata filter.")
        return self.knowledge_service.search(
            normalized_question,
            top_k=top_k,
            metadata_filter=metadata_filter or None,
        )
