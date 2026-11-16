"""MCP server exposing NovaBank capabilities as the central tool interface (MCP SDK 2.x).

Two transports:

* **stdio** – one subprocess per request; the caller's MCP token arrives in
  ``NOVABANK_ACCESS_TOKEN`` and is verified once at start-up.
* **Streamable HTTP** – a separate, stateless server. It acts as an OAuth 2.1 *resource
  server*: every request needs ``Authorization: Bearer <token>`` with audience
  ``MCP_AUDIENCE``; missing or invalid tokens get 401 with a pointer to the protected-resource
  metadata (RFC 9728). The verified identity reaches every tool, which applies the same
  authorization as in the API.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from secure_enterprise_ai_assistant import __version__
from secure_enterprise_ai_assistant.core.cli import GermanArgumentParser
from secure_enterprise_ai_assistant.core.logs import configure_logging, get_logger
from secure_enterprise_ai_assistant.core.settings import Settings, get_settings
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.models.tools import (
    ComplianceCheckResult,
    CustomerCaseResult,
    FinancialAnalysisResult,
)
from secure_enterprise_ai_assistant.security.access import AccessDeniedError
from secure_enterprise_ai_assistant.security.models import Principal, Role
from secure_enterprise_ai_assistant.security.tokens import (
    InvalidTokenError,
    TokenService,
    mcp_token_service,
)
from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError

if TYPE_CHECKING:
    from starlette.applications import Starlette

ACCESS_TOKEN_VARIABLE = "NOVABANK_ACCESS_TOKEN"
PrincipalProvider = Callable[[], Principal]
# Failures whose (German, value-free) message is meant for the caller.
EXPECTED_ERRORS = (CaseNotFoundError, AccessDeniedError, ValueError)

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
        if isinstance(exc, EXPECTED_ERRORS):
            # Anticipated failures carry safe German messages written for the caller. MCP 2.x
            # passes only ToolError text on; every other exception reaches the client as a
            # generic "Error executing tool", so internals never leak.
            raise ToolError(str(exc)) from exc
        raise
    logger.info(
        "mcp_tool_completed",
        extra={"tool": tool, "duration_ms": round((time.perf_counter() - started) * 1000, 1)},
    )


def token_service_from_settings() -> TokenService | None:
    """The MCP token verifier of the current settings, or ``None`` without a JWT secret."""
    return mcp_token_service(get_settings())


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


class JwtTokenVerifier:
    """MCP ``TokenVerifier`` backed by the project's strict JWT validation."""

    def __init__(self, tokens: TokenService, resource: str) -> None:
        self._tokens = tokens
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            principal = self._tokens.verify(token)
        except InvalidTokenError:
            logger.warning("mcp_token_rejected")
            return None
        assert principal.role is not None  # verify() only returns authenticated principals
        return AccessToken(
            token=token,
            client_id=self._tokens.issuer,
            scopes=[],
            subject=principal.username,
            claims={"role": principal.role.value, "team": principal.team},
        )


def principal_from_access_token() -> Principal:
    """Principal of the current HTTP request, from the token the bearer middleware verified."""
    access = get_access_token()
    if access is None or access.subject is None:
        return Principal.anonymous()
    claims = access.claims or {}
    try:
        return Principal(
            username=access.subject,
            role=Role(str(claims.get("role"))),
            team=claims.get("team"),
        )
    except ValueError:
        return Principal.anonymous()


def create_mcp_server(
    tool_service: MCPToolService | None = None,
    principal_provider: PrincipalProvider | None = None,
    token_verifier: JwtTokenVerifier | None = None,
    auth: AuthSettings | None = None,
) -> MCPServer:
    """Create a real MCP server with four allowlisted, authorization-aware tools."""
    service = tool_service or MCPToolService.build_default()
    current_principal = principal_provider or principal_from_environment
    server: MCPServer = MCPServer(
        "NovaBank Secure Enterprise Tools",
        version=__version__,
        instructions=(
            "Nutze nur diese Werkzeuge für synthetische NovaBank-Fälle, deterministische "
            "Finanzanalyse, Compliance-Prüfung und die Suche in internen Richtlinien mit "
            "Quellenangabe."
        ),
        token_verifier=token_verifier,
        auth=auth,
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
            "Berechnet monatliche Rate, Gesamtrückzahlung, Gesamtzins, DTI und Verpflichtungen "
            "nach Kredit für einen synthetischen Fall deterministisch."
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
            "Kreditregelwerk der NovaBank und leitet eine Empfehlung ab."
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


def create_http_app(
    settings: Settings | None = None, tool_service: MCPToolService | None = None
) -> Starlette:
    """Stateless Streamable HTTP app that only accepts MCP tokens (resource-server role)."""
    settings = settings or get_settings()
    tokens = mcp_token_service(settings)
    if tokens is None:
        raise RuntimeError(
            "JWT_SECRET ist nicht gesetzt. Ohne Schlüssel startet der MCP-HTTP-Server nicht."
        )
    server = create_mcp_server(
        tool_service,
        principal_provider=principal_from_access_token,
        token_verifier=JwtTokenVerifier(tokens, settings.mcp_server_url),
        auth=AuthSettings.model_validate(
            {
                # The API issues the tokens; it is named as authorization server in the
                # protected-resource metadata. It is not a full OAuth 2.1 authorization server.
                "issuer_url": settings.api_base_url,
                "resource_server_url": settings.mcp_server_url,
                "required_scopes": [],
                # JwtTokenVerifier checks the audience (MCP_AUDIENCE) itself.
                "validate_token_resource": False,
            }
        ),
    )
    return server.streamable_http_app(
        stateless_http=True, json_response=True, host=settings.mcp_host
    )


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server; logs go to stderr because stdout carries MCP in stdio mode."""
    settings = get_settings()
    parser = GermanArgumentParser(
        prog="novabank-mcp",
        description="MCP-Server mit den NovaBank-Werkzeugen (fiktive Daten, MCP SDK 2.x).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=settings.mcp_transport,
        help="stdio: ein Prozess pro Anfrage; http: eigener Server (Streamable HTTP)",
    )
    parser.add_argument(
        "--host", default=settings.mcp_host, metavar="ADRESSE", help="Adresse im HTTP-Betrieb"
    )
    parser.add_argument(
        "--port", type=int, default=settings.mcp_port, metavar="PORT", help="Port im HTTP-Betrieb"
    )
    arguments = parser.parse_args(argv)
    configure_logging(settings.log_level)

    if arguments.transport == "http":
        import uvicorn

        logger.info(
            "mcp_http_server_started", extra={"host": arguments.host, "port": arguments.port}
        )
        uvicorn.run(create_http_app(settings), host=arguments.host, port=arguments.port)
        return

    principal = principal_from_environment()
    logger.info("mcp_server_started", extra={"user": principal.username})
    create_mcp_server(principal_provider=lambda: principal).run(transport="stdio")


if __name__ == "__main__":
    main()
