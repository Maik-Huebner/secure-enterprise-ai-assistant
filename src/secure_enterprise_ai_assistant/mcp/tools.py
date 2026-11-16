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
from secure_enterprise_ai_assistant.services import (
    ComplianceService,
    CustomerCaseRepository,
    FinancialAnalysisService,
)

CASE_ID_PATTERN = re.compile(r"^CASE-\d{5}$")
ALLOWED_METADATA_FILTERS = {"document_id", "owner", "version"}
DOCUMENT_ID_PATTERN = re.compile(r"^NB-[A-Z]+-\d{3}$")


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
        return cls.build(KnowledgeService.from_settings(get_settings()))

    @classmethod
    def build(cls, knowledge_service: KnowledgeService) -> MCPToolService:
        """Build the tool boundary around an explicitly chosen knowledge service."""
        return cls(
            repository=CustomerCaseRepository.from_json(),
            financial_service=FinancialAnalysisService(),
            compliance_service=ComplianceService.from_json(),
            knowledge_service=knowledge_service,
        )

    @staticmethod
    def _case_id(case_id: str) -> str:
        if not isinstance(case_id, str):
            raise ValueError("case_id muss eine Zeichenkette sein.")
        normalized = case_id.strip().upper()
        if not CASE_ID_PATTERN.fullmatch(normalized):
            raise ValueError("case_id muss das Format CASE- mit fünf Ziffern haben.")
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
        if not isinstance(question, str):
            raise ValueError("question muss eine Zeichenkette sein.")
        normalized_question = validate_user_query(question)
        if len(normalized_question) > 1000:
            raise ValueError("question darf höchstens 1000 Zeichen enthalten.")
        if type(top_k) is not int or not 1 <= top_k <= 10:
            raise ValueError("top_k muss zwischen 1 und 10 liegen.")
        supplied_filters = {
            "document_id": document_id,
            "owner": owner,
            "version": version,
        }
        metadata_filter: dict[str, str] = {}
        for key, value in supplied_filters.items():
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(f"Der Filter {key} muss eine Zeichenkette sein.")
            normalized = value.strip()
            if not normalized:
                continue
            if len(normalized) > 120 or any(ord(character) < 32 for character in normalized):
                raise ValueError(f"Der Filter {key} enthält unzulässige Zeichen.")
            metadata_filter[key] = normalized
        if not metadata_filter.keys() <= ALLOWED_METADATA_FILTERS:
            raise ValueError("Nicht unterstützter Metadatenfilter.")
        if document_id is not None and "document_id" in metadata_filter:
            metadata_filter["document_id"] = metadata_filter["document_id"].upper()
            if not DOCUMENT_ID_PATTERN.fullmatch(metadata_filter["document_id"]):
                raise ValueError("Der Filter document_id muss das Format NB-<TYP>-000 haben.")
        return self.knowledge_service.search(
            normalized_question,
            top_k=top_k,
            metadata_filter=metadata_filter or None,
        )
