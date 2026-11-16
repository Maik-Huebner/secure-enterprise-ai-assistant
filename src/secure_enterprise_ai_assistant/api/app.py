"""FastAPI backend: the single entry point for the UI and for other systems (PHP, Java, ...).

Security model:
- JWT bearer tokens (HS256, short-lived), Argon2id passwords, three roles;
- authorization in code and inside every MCP tool; forbidden cases look like unknown cases;
- knowledge search filters documents *before* ranking;
- rate limits, restrictive CORS, security headers, hash-chained audit log;
- errors as RFC 9457 problem details in German without internal details or echoed input.

No ``from __future__ import annotations`` here: FastAPI must evaluate the ``Annotated``
dependency types of the endpoints defined inside :func:`create_app` at definition time.
"""

import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from secure_enterprise_ai_assistant import __version__
from secure_enterprise_ai_assistant.api.middleware import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from secure_enterprise_ai_assistant.api.schemas import (
    CaseSummary,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    LoginRequest,
    MeResponse,
    Problem,
    ReadinessResponse,
    ReviewDecisionRequest,
    ReviewDetail,
    ReviewSummary,
    SearchRequest,
    TokenResponse,
)
from secure_enterprise_ai_assistant.core.logs import (
    configure_logging,
    current_request_id,
    get_logger,
)
from secure_enterprise_ai_assistant.core.settings import Settings, get_settings
from secure_enterprise_ai_assistant.graph.assistant import AssistantResult, AssistantService
from secure_enterprise_ai_assistant.graph.reviews import ReviewRecord, ReviewStore
from secure_enterprise_ai_assistant.guardrails import UnsafeInputError, validate_user_query
from secure_enterprise_ai_assistant.mcp.tools import MCPToolService
from secure_enterprise_ai_assistant.models.knowledge import KnowledgeSearchResponse
from secure_enterprise_ai_assistant.models.tools import (
    ComplianceCheckResult,
    CustomerCaseResult,
    FinancialAnalysisResult,
)
from secure_enterprise_ai_assistant.observability import build_tracing
from secure_enterprise_ai_assistant.rag.embeddings import EmbeddingUnavailableError
from secure_enterprise_ai_assistant.security import AccessDeniedError, AccessPolicy, Principal
from secure_enterprise_ai_assistant.security.audit import AuditLog
from secure_enterprise_ai_assistant.security.rate_limit import SlidingWindowLimiter
from secure_enterprise_ai_assistant.security.tokens import (
    InvalidTokenError,
    TokenService,
    api_token_service,
    mcp_token_service,
)
from secure_enterprise_ai_assistant.security.users import UserStore
from secure_enterprise_ai_assistant.services.errors import CaseNotFoundError

logger = get_logger(__name__)
SOURCE_PATTERN = re.compile(r"\bNB-[A-Z]+-\d{3}\b")


@dataclass
class ApiContext:
    """Everything the endpoints need; replaceable in tests."""

    settings: Settings
    tokens: TokenService
    mcp_tokens: TokenService
    users: UserStore
    policy: AccessPolicy
    tools: MCPToolService
    audit: AuditLog
    assistant: AssistantService
    reviews: ReviewStore
    login_limiter: SlidingWindowLimiter = field(init=False)
    chat_limiter: SlidingWindowLimiter = field(init=False)
    api_limiter: SlidingWindowLimiter = field(init=False)

    def __post_init__(self) -> None:
        self.login_limiter = SlidingWindowLimiter(self.settings.login_rate_limit_per_minute, 60)
        self.chat_limiter = SlidingWindowLimiter(self.settings.chat_rate_limit_per_minute, 60)
        self.api_limiter = SlidingWindowLimiter(self.settings.api_rate_limit_per_minute, 60)


def build_context(settings: Settings | None = None) -> ApiContext:
    """Build the production context. Refuses to start without a JWT secret."""
    settings = settings or get_settings()
    if settings.jwt_secret is None:
        raise RuntimeError(
            "JWT_SECRET ist nicht gesetzt. Ohne Schlüssel startet die API nicht. Beispiel: "
            "export JWT_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
        )
    tools = MCPToolService.build_default()
    tokens, mcp_tokens = api_token_service(settings), mcp_token_service(settings)
    assert tokens is not None and mcp_tokens is not None
    return ApiContext(
        settings=settings,
        tokens=tokens,
        mcp_tokens=mcp_tokens,
        users=UserStore(settings.resolved_users_file),
        policy=tools.access_policy,
        tools=tools,
        audit=AuditLog(settings.resolved_audit_log),
        assistant=AssistantService.with_sqlite(
            settings.graph_checkpoint_path, settings=settings, tracing=build_tracing(settings)
        ),
        reviews=ReviewStore(settings.review_index_path),
    )


def _problem(
    status: int, title: str, detail: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = Problem(title=title, status=status, detail=detail, request_id=current_request_id())
    return JSONResponse(
        body.model_dump(),
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unbekannt"


def _enforce(limiter: SlidingWindowLimiter, key: str) -> None:
    allowed, retry_after = limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Zu viele Anfragen. Bitte später erneut versuchen.",
            headers={"Retry-After": str(retry_after)},
        )


def create_app(context: ApiContext | None = None) -> FastAPI:
    """Create the FastAPI application."""
    ctx = context or build_context()
    settings = ctx.settings

    def _mcp_token(principal: Principal) -> str:
        # A fresh token bound to the MCP resource; the API bearer token is never forwarded.
        return ctx.mcp_tokens.issue(principal)[0]

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        ctx.assistant.close()  # flush and close the checkpoint database on shutdown

    app = FastAPI(
        lifespan=lifespan,
        title="NovaBank Secure Enterprise AI Assistant – API",
        version=__version__,
        description=(
            "Lokale, abgesicherte Entscheidungsunterstützung für fiktive NovaBank-Kreditfälle. "
            "Alle Daten sind synthetisch. Anmeldung über `POST /v1/auth/token`, danach "
            "`Authorization: Bearer <token>`."
        ),
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.hsts_enabled)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    bearer = HTTPBearer(auto_error=False, description="JWT aus POST /v1/auth/token")

    # ----- error handling -------------------------------------------------------------------
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        titles = {
            401: "Nicht angemeldet",
            403: "Keine Berechtigung",
            404: "Nicht gefunden",
            429: "Zu viele Anfragen",
        }
        return _problem(
            exc.status_code,
            titles.get(exc.status_code, "Fehler"),
            str(exc.detail),
            dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations only: the submitted values (e.g. passwords) are never echoed.
        fields = sorted(
            {".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()}
        )
        return _problem(
            422, "Ungültige Anfrage", f"Bitte diese Felder prüfen: {', '.join(fields)}."
        )

    @app.exception_handler(AccessDeniedError)
    async def access_denied(_request: Request, exc: AccessDeniedError) -> JSONResponse:
        return _problem(403, "Keine Berechtigung", str(exc))

    @app.exception_handler(CaseNotFoundError)
    async def case_not_found(_request: Request, exc: CaseNotFoundError) -> JSONResponse:
        return _problem(404, "Nicht gefunden", str(exc))

    @app.exception_handler(UnsafeInputError)
    async def unsafe_input(_request: Request, exc: UnsafeInputError) -> JSONResponse:
        return _problem(400, "Anfrage abgelehnt", str(exc))

    @app.exception_handler(EmbeddingUnavailableError)
    async def embeddings_down(_request: Request, exc: EmbeddingUnavailableError) -> JSONResponse:
        logger.error("embedding_unavailable")
        return _problem(
            503, "Dienst nicht verfügbar", "Das lokale Embedding-Modell ist nicht erreichbar."
        )

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("api_unhandled_error", extra={"error_type": type(exc).__name__})
        return _problem(500, "Interner Fehler", "Die Anfrage konnte nicht verarbeitet werden.")

    # ----- authentication -------------------------------------------------------------------
    def current_principal(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "Anmeldung erforderlich.", {"WWW-Authenticate": "Bearer"})
        try:
            principal = ctx.tokens.verify(credentials.credentials)
        except InvalidTokenError as exc:
            raise HTTPException(401, str(exc), {"WWW-Authenticate": "Bearer"}) from exc
        # Deleted or deactivated users lose access immediately, not only when the token expires.
        if not any(
            user.username == principal.username and user.active for user in ctx.users.list_users()
        ):
            raise HTTPException(
                401, "Benutzer ist nicht mehr aktiv.", {"WWW-Authenticate": "Bearer"}
            )
        _enforce(ctx.api_limiter, f"user:{principal.username}")
        return principal

    PrincipalDep = Annotated[Principal, Depends(current_principal)]

    def safe_tool_call[T](callable_: Callable[[], T]) -> T:
        try:
            return callable_()
        except ValueError as exc:
            if type(exc) is ValueError:  # our own input messages; never pydantic internals
                raise HTTPException(400, str(exc)) from exc
            raise

    # ----- endpoints ------------------------------------------------------------------------
    @app.get("/health", response_model=HealthResponse, tags=["Betrieb"])
    def health() -> HealthResponse:
        """Lebenszeichen ohne Abhängigkeiten (Liveness)."""
        return HealthResponse(status="ok")

    @app.get("/ready", response_model=ReadinessResponse, tags=["Betrieb"])
    def ready() -> ReadinessResponse:
        """Bereitschaft: Suchindex geladen und Ollama erreichbar (Readiness)."""
        checks = {"knowledge_index": bool(ctx.tools.knowledge_service.document_ids())}
        try:
            response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.0)
            checks["ollama"] = response.is_success
        except httpx.HTTPError:
            checks["ollama"] = False
        return ReadinessResponse(
            status="ready" if all(checks.values()) else "degraded", checks=checks
        )

    @app.post("/v1/auth/token", response_model=TokenResponse, tags=["Anmeldung"])
    def login(body: LoginRequest, request: Request) -> TokenResponse:
        """Anmeldung mit Benutzername und Passwort; liefert ein kurzlebiges JWT."""
        _enforce(ctx.login_limiter, f"ip:{_client_ip(request)}")
        principal = ctx.users.authenticate(body.username, body.password)
        if principal is None:
            ctx.audit.record("login_failed", Principal.anonymous(), username=body.username[:64])
            raise HTTPException(
                401, "Benutzername oder Passwort ist falsch.", {"WWW-Authenticate": "Bearer"}
            )
        token, expires_in = ctx.tokens.issue(principal)
        ctx.audit.record("login_succeeded", principal)
        return TokenResponse(access_token=token, expires_in=expires_in)

    @app.get("/v1/me", response_model=MeResponse, tags=["Anmeldung"])
    def me(principal: PrincipalDep) -> MeResponse:
        """Eigene Rolle und Rechte."""
        return MeResponse(
            username=principal.username,
            role=principal.role.value if principal.role else "",
            team=principal.team,
            may_request_decision_brief=ctx.policy.can_request_decision_brief(principal),
            document_classes=sorted(ctx.policy.document_classes(principal)),
        )

    @app.get("/v1/cases", response_model=list[CaseSummary], tags=["Fälle"])
    def list_cases(principal: PrincipalDep) -> list[CaseSummary]:
        """Fälle, die der angemeldete Benutzer sehen darf."""
        summaries = []
        for case_id in ctx.tools.list_case_ids(principal):
            case = ctx.tools.get_customer_case(case_id, principal=principal).case
            summaries.append(
                CaseSummary(
                    case_id=case.case_id,
                    customer_name=case.customer.full_name,
                    requested_amount_eur=case.application.requested_amount_eur,
                    term_months=case.application.term_months,
                )
            )
        ctx.audit.record("cases_listed", principal, count=len(summaries))
        return summaries

    def _case_call[T](event: str, principal: Principal, case_id: str, call: Callable[[], T]) -> T:
        try:
            result = safe_tool_call(call)
        except CaseNotFoundError:
            ctx.audit.record(f"{event}_not_found", principal, case_id=case_id[:20])
            raise
        ctx.audit.record(event, principal, case_id=case_id[:20])
        return result

    @app.get("/v1/cases/{case_id}", response_model=CustomerCaseResult, tags=["Fälle"])
    def get_case(case_id: str, principal: PrincipalDep) -> CustomerCaseResult:
        """Validierte Falldaten. Fremde Fälle sind von unbekannten nicht zu unterscheiden."""
        return _case_call(
            "case_read",
            principal,
            case_id,
            lambda: ctx.tools.get_customer_case(case_id, principal=principal),
        )

    @app.get(
        "/v1/cases/{case_id}/financials", response_model=FinancialAnalysisResult, tags=["Fälle"]
    )
    def get_financials(case_id: str, principal: PrincipalDep) -> FinancialAnalysisResult:
        """Deterministische Finanzkennzahlen (Annuität, DTI)."""
        return _case_call(
            "financials_read",
            principal,
            case_id,
            lambda: ctx.tools.analyze_financial_case(case_id, principal=principal),
        )

    @app.get("/v1/cases/{case_id}/compliance", response_model=ComplianceCheckResult, tags=["Fälle"])
    def get_compliance(case_id: str, principal: PrincipalDep) -> ComplianceCheckResult:
        """Ergebnisse aller Compliance-Regeln."""
        return _case_call(
            "compliance_read",
            principal,
            case_id,
            lambda: ctx.tools.check_compliance(case_id, principal=principal),
        )

    @app.post("/v1/search", response_model=KnowledgeSearchResponse, tags=["Wissen"])
    def search(body: SearchRequest, principal: PrincipalDep) -> KnowledgeSearchResponse:
        """Suche in den Richtlinien, die der Benutzer lesen darf (Filter vor dem Ranking)."""
        response: KnowledgeSearchResponse = safe_tool_call(
            lambda: ctx.tools.search_internal_knowledge(
                body.question, principal=principal, top_k=body.top_k, document_id=body.document_id
            )
        )
        ctx.audit.record(
            "knowledge_searched",
            principal,
            question_length=len(body.question),
            documents=sorted({item.chunk.document_id for item in response.results}),
            out_of_scope=response.out_of_scope,
        )
        return response

    def _chat_response(result: AssistantResult) -> ChatResponse:
        return ChatResponse(
            thread_id=result.thread_id,
            status=result.status,
            answer=result.answer,
            intent=result.route.intent.value,
            case_id=result.route.case_id,
            routing_method=result.route.routing_method,
            execution_mode=result.execution_mode,
            sources=sorted(set(SOURCE_PATTERN.findall(result.answer))),
            trace=result.trace,
        )

    @app.post("/v1/chat", response_model=ChatResponse, tags=["Assistent"])
    def chat(body: ChatRequest, principal: PrincipalDep, request: Request) -> ChatResponse:
        """Frage an den Assistenten. Entscheidungsvorlagen warten auf eine zweite Person."""
        _enforce(ctx.chat_limiter, f"user:{principal.username}")
        # Defense in depth: the API filters input itself before the workflow sees it.
        message = validate_user_query(body.message)
        try:
            result = ctx.assistant.run(message, principal, _mcp_token(principal))
        except AccessDeniedError:
            ctx.audit.record("chat_denied", principal, message_length=len(body.message))
            raise
        if result.status == "awaiting_approval" and result.route.case_id:
            ctx.reviews.open(result.thread_id, result.route.case_id, principal.username)
            ctx.audit.record(
                "decision_brief_requested",
                principal,
                case_id=result.route.case_id,
                thread_id=result.thread_id,
            )
        else:
            ctx.audit.record(
                "chat_answered",
                principal,
                intent=result.route.intent.value,
                case_id=result.route.case_id,
                execution_mode=result.execution_mode,
            )
        return _chat_response(result)

    def _require_reviewer(principal: Principal) -> None:
        if not ctx.policy.can_request_decision_brief(principal):
            raise AccessDeniedError("Freigaben sehen und erteilen nur Prüferinnen und Prüfer.")

    @app.get("/v1/reviews", response_model=list[ReviewSummary], tags=["Freigabe"])
    def list_reviews(principal: PrincipalDep) -> list[ReviewSummary]:
        """Offene Entscheidungsvorlagen, die auf eine zweite Person warten."""
        _require_reviewer(principal)
        return [
            ReviewSummary(
                **record.model_dump(
                    include={"thread_id", "case_id", "requested_by", "requested_at", "status"}
                )
            )
            for record in ctx.reviews.pending()
        ]

    def _pending(thread_id: str) -> ReviewRecord:
        record = ctx.reviews.get(thread_id)
        if record is None or record.status != "pending":
            raise HTTPException(404, "Keine offene Freigabe mit dieser ID.")
        return record

    @app.get("/v1/reviews/{thread_id}", response_model=ReviewDetail, tags=["Freigabe"])
    def get_review(thread_id: str, principal: PrincipalDep) -> ReviewDetail:
        """Entwurf einer offenen Entscheidungsvorlage."""
        _require_reviewer(principal)
        record = _pending(thread_id)
        return ReviewDetail(
            thread_id=record.thread_id,
            case_id=record.case_id,
            requested_by=record.requested_by,
            requested_at=record.requested_at,
            status=record.status,
            draft=ctx.assistant.draft(thread_id),
        )

    @app.post("/v1/reviews/{thread_id}", response_model=ChatResponse, tags=["Freigabe"])
    def decide_review(
        thread_id: str, body: ReviewDecisionRequest, principal: PrincipalDep, request: Request
    ) -> ChatResponse:
        """Freigabe oder Ablehnung durch eine zweite Person (Vier-Augen-Prinzip)."""
        _require_reviewer(principal)
        record = _pending(thread_id)
        if record.requested_by == principal.username:
            ctx.audit.record("decision_brief_self_approval_denied", principal, thread_id=thread_id)
            raise AccessDeniedError(
                "Vier-Augen-Prinzip: Die anfragende Person darf nicht selbst freigeben."
            )
        result = ctx.assistant.resume(
            thread_id,
            body.decision == "approve",
            body.comment,
            principal,
            _mcp_token(principal),
        )
        ctx.reviews.close(thread_id, body.decision == "approve", principal.username)
        ctx.audit.record(
            "decision_brief_approved" if body.decision == "approve" else "decision_brief_rejected",
            principal,
            case_id=record.case_id,
            thread_id=thread_id,
            requested_by=record.requested_by,
        )
        return _chat_response(result)

    return app


def main() -> None:
    """Start the API with Uvicorn on the configured (loopback by default) address."""
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        app = create_app()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        server_header=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
