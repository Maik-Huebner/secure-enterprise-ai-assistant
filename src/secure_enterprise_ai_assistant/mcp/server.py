"""FastMCP server exposing NovaBank capabilities as the central tool interface."""

from __future__ import annotations

import mcp.server.fastmcp.server as fastmcp_server
from mcp.server.fastmcp import FastMCP

from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.models.tools import (
    ComplianceCheckResult,
    CustomerCaseResult,
    FinancialAnalysisResult,
)

# MCP SDK 1.28 leaves the generic lifespan annotation unresolved on Python 3.13.
# Rebuilding with the defining module's namespace follows Pydantic's prescribed fix.
fastmcp_server.Settings.model_rebuild(_types_namespace=vars(fastmcp_server))


def create_mcp_server(tool_service: MCPToolService | None = None) -> FastMCP:
    """Create a real stdio/HTTP-capable MCP server with four allowlisted tools."""
    service = tool_service or MCPToolService.build_default()
    server = FastMCP(
        "NovaBank Secure Enterprise Tools",
        instructions=(
            "Use only these tools for synthetic NovaBank cases, deterministic financial "
            "analysis, compliance checks, and attributable internal knowledge retrieval."
        ),
    )

    @server.tool(
        name="get_customer_case",
        description="Load one fully synthetic NovaBank credit case by CASE-00000 identifier.",
        structured_output=True,
    )
    def get_customer_case(case_id: str) -> CustomerCaseResult:
        return service.get_customer_case(case_id)

    @server.tool(
        name="analyze_financial_case",
        description=(
            "Calculate monthly payment, repayment, interest, and DTI metrics "
            "deterministically for a synthetic case."
        ),
        structured_output=True,
    )
    def analyze_financial_case(case_id: str) -> FinancialAnalysisResult:
        return service.analyze_financial_case(case_id)

    @server.tool(
        name="check_compliance",
        description=(
            "Evaluate a synthetic case against versioned NovaBank compliance "
            "and lending-policy rules."
        ),
        structured_output=True,
    )
    def check_compliance(case_id: str) -> ComplianceCheckResult:
        return service.check_compliance(case_id)

    @server.tool(
        name="search_internal_knowledge",
        description=(
            "Search synthetic NovaBank policy documents with hybrid retrieval "
            "and return exact source metadata."
        ),
        structured_output=True,
    )
    def search_internal_knowledge(
        question: str,
        top_k: int = 5,
        document_id: str | None = None,
        owner: str | None = None,
        version: str | None = None,
    ) -> KnowledgeSearchResponse:
        return service.search_internal_knowledge(
            question,
            top_k=top_k,
            document_id=document_id,
            owner=owner,
            version=version,
        )

    return server


def main() -> None:
    """Run the MCP server over stdio for CrewAI and other local clients."""
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
