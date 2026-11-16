"""Short-lived JWT access tokens (HS256) with strict validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from secure_enterprise_ai_assistant.core.settings import Settings
from secure_enterprise_ai_assistant.security.models import Principal, Role

ALGORITHM = "HS256"
MIN_SECRET_BYTES = 32


class InvalidTokenError(ValueError):
    """Raised for missing, expired, tampered or otherwise unacceptable tokens."""


class TokenService:
    """Issue and verify access tokens. The algorithm is fixed; 'none' is never accepted."""

    def __init__(self, secret: str, issuer: str, audience: str, ttl_minutes: int) -> None:
        if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET muss mindestens {MIN_SECRET_BYTES} Bytes lang sein "
                "(z. B. python -c 'import secrets; print(secrets.token_urlsafe(48))')."
            )
        self._secret = secret
        self.issuer = issuer
        self.audience = audience
        self.ttl = timedelta(minutes=ttl_minutes)

    def issue(self, principal: Principal, now: datetime | None = None) -> tuple[str, int]:
        """Return a signed token and its lifetime in seconds."""
        if principal.role is None:
            raise ValueError("Für anonyme Aufrufer werden keine Tokens ausgestellt.")
        issued = now or datetime.now(tz=UTC)
        claims = {
            "sub": principal.username,
            "role": principal.role.value,
            "team": principal.team,
            "iss": self.issuer,
            "aud": self.audience,
            "iat": issued,
            "nbf": issued,
            "exp": issued + self.ttl,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM), int(self.ttl.total_seconds())

    def verify(self, token: str) -> Principal:
        """Return the principal of a valid token or raise :class:`InvalidTokenError`."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]},
            )
            return Principal(
                username=str(claims["sub"]),
                role=Role(claims["role"]),
                team=claims.get("team"),
            )
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise InvalidTokenError("Ungültiges oder abgelaufenes Zugriffstoken.") from exc


def api_token_service(settings: Settings) -> TokenService | None:
    """Tokens for the REST API (audience ``JWT_AUDIENCE``); ``None`` without a secret."""
    if settings.jwt_secret is None:
        return None
    return TokenService(
        settings.jwt_secret.get_secret_value(),
        settings.jwt_issuer,
        settings.jwt_audience,
        settings.jwt_ttl_minutes,
    )


def mcp_token_service(settings: Settings) -> TokenService | None:
    """Short-lived tokens for the MCP server (audience ``MCP_AUDIENCE``).

    The API never forwards its own bearer token to MCP ("token passthrough" is forbidden by the
    MCP authorization spec). It issues a separate token bound to the MCP resource instead, so a
    token stolen from the tool layer is useless at the API and vice versa.
    """
    if settings.jwt_secret is None:
        return None
    return TokenService(
        settings.jwt_secret.get_secret_value(),
        settings.jwt_issuer,
        settings.mcp_audience,
        settings.mcp_token_ttl_minutes,
    )
