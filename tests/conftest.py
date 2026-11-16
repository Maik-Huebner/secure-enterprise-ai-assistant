"""Test-wide configuration: fast, offline, deterministic, with test-only credentials."""

import os

# Must be set before any settings object is created. Subprocesses (MCP stdio server, UI probe)
# receive these through the allowlisted MCP environment.
os.environ["EMBEDDING_BACKEND"] = "hashing"
# Test-only signing key; never used outside the test suite.
os.environ["JWT_SECRET"] = "test-only-signing-key-not-for-any-deployment-0123456789"

from secure_enterprise_ai_assistant.core.settings import get_settings  # noqa: E402
from secure_enterprise_ai_assistant.mcp.server import token_service_from_settings  # noqa: E402
from secure_enterprise_ai_assistant.security.models import Principal, Role  # noqa: E402

CASE_WORKER_NORD = Principal(username="sb.nord", role=Role.CASE_WORKER, team="team-nord")
CASE_WORKER_SUED = Principal(username="sb.sued", role=Role.CASE_WORKER, team="team-sued")
REVIEWER = Principal(username="pruefer", role=Role.REVIEWER)
ADMIN = Principal(username="admin", role=Role.ADMIN)


def token_for(principal: Principal) -> str:
    """Issue a real signed token with the test key."""
    get_settings.cache_clear()
    service = token_service_from_settings()
    assert service is not None
    return service.issue(principal)[0]
