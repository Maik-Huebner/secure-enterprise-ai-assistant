"""FastMCP server exposing NovaBank capabilities as the central tool interface."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import mcp.server.fastmcp.server as fastmcp_server
from mcp.server.fastmcp import FastMCP

from secure_enterprise_ai_assistant.core.logs import configure_logging, get_logger
from secure_enterprise_ai_assistant.core.settings import get_settings
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.models.tools import (
    ComplianceCheckResult,
    CustomerCaseResult,
    FinancialAnalysisResult,
)
from secure_enterprise_ai_assistant.security.models import Principal
from secure_enterprise_ai_assistant.security.tokens import InvalidTokenError, TokenService

ACCESS_TOKEN_VARIABLE = "NOVABANK_ACCESS_TOKEN"
PrincipalProvider = Callable[[], Principal]

# MCP SDK 1.28 leaves the generic lifespan annotation unresolved on Python 3.13.
# Rebuilding with the defining module's namespace follows Pydantic's prescribed fix.
fastmcp_server.Settings.model_rebuild(_types_namespace=vars(fastmcp_server))

logger = get_logger(__name__)


@contextmanager
def _logged_tool_call(tool: str) -> Iterator[None]:
    """Log tool name, outcome, and duration; arguments are not logged."""
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        logger.warning(
            "mcp_tool_failed",
            extra={
                "tool": tool,
                "error_type": type(exc).__name__,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        raise
    logger.info(
        "mcp_tool_completed",
        extra={"tool": tool, "duration_ms": round((time.perf_counter() - started) * 1000, 1)},
    )


def token_service_from_settings() -> TokenService | None:
    """Return the token verifier, or ``None`` if no JWT secret is configured."""
    settings = get_settings()
    if settings.jwt_secret is None:
        return None
    return TokenService(
        settings.jwt_secret.get_secret_value(),
        settings.jwt_issuer,
        settings.jwt_audience,
        settings.jwt_ttl_minutes,
    )


def principal_from_environment() -> Principal:
    """Resolve the caller of a stdio server from its access token; anonymous otherwise."""
    token = os.environ.get(ACCESS_TOKEN_VARIABLE, "")
    verifier = token_service_from_settings()
    if not token or verifier is None:
        return Principal.anonymous()
    try:
        return verifier.verify(token)
    except InvalidTokenError:
        logger.warning("mcp_token_rejected")
        return Principal.anonymous()


def create_mcp_server(
    tool_service: MCPToolService | None = None,
    principal_provider: PrincipalProvider | None = None,
) -> FastMCP:
    """Create a real MCP server with four allowlisted, authorization-aware tools."""
    service = tool_service or MCPToolService.build_default()
    current_principal = principal_provider or principal_from_environment
    server = FastMCP(
        "NovaBank Secure Enterprise Tools",
        instructions=(
            "Nutze nur diese Werkzeuge für synthetische NovaBank-Fälle, deterministische "
            "Finanzanalyse, Compliance-Prüfung und die Suche in internen Richtlinien mit "
            "Quellenangabe."
        ),
    )

    @server.tool(
        name="get_customer_case",
        description="Lädt einen synthetischen NovaBank-Kreditfall über die ID CASE-00000.",
        structured_output=True,
    )
    def get_customer_case(case_id: str) -> CustomerCaseResult:
        with _logged_tool_call("get_customer_case"):
            return service.get_customer_case(case_id, principal=current_principal())

    @server.tool(
        name="analyze_financial_case",
        description=(
            "Berechnet monatliche Rate, Gesamtrückzahlung, Gesamtzins und DTI für einen "
            "synthetischen Fall deterministisch."
        ),
        structured_output=True,
    )
    def analyze_financial_case(case_id: str) -> FinancialAnalysisResult:
        with _logged_tool_call("analyze_financial_case"):
            return service.analyze_financial_case(case_id, principal=current_principal())

    @server.tool(
        name="check_compliance",
        description=(
            "Prüft einen synthetischen Fall gegen das versionierte Compliance- und "
            "Kreditregelwerk der NovaBank."
        ),
        structured_output=True,
    )
    def check_compliance(case_id: str) -> ComplianceCheckResult:
        with _logged_tool_call("check_compliance"):
            return service.check_compliance(case_id, principal=current_principal())

    @server.tool(
        name="search_internal_knowledge",
        description=(
            "Durchsucht die synthetischen Richtlinien der NovaBank und liefert Textstellen "
            "mit genauer Quellenangabe."
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
        with _logged_tool_call("search_internal_knowledge"):
            return service.search_internal_knowledge(
                question,
                principal=current_principal(),
                top_k=top_k,
                document_id=document_id,
                owner=owner,
                version=version,
            )

    return server


def main() -> None:
    """Run the MCP server over stdio; logs go to stderr because stdout carries MCP.

    The caller is resolved once from ``NOVABANK_ACCESS_TOKEN``; without a valid token every
    tool call is denied.
    """
    configure_logging(get_settings().log_level)
    principal = principal_from_environment()
    logger.info("mcp_server_started", extra={"user": principal.username})
    create_mcp_server(principal_provider=lambda: principal).run(transport="stdio")


if __name__ == "__main__":
    main()
