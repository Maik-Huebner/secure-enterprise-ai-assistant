"""Secret detection rules of the repository audit."""

import pytest

from secure_enterprise_ai_assistant.quality.repository_audit import SECRET_PATTERNS

# Fixtures are assembled at runtime so that the repository itself never contains them literally.
KEY = "JWT_" + "SECRET"


@pytest.mark.parametrize(
    "text",
    [
        f"{KEY}=abcdefghijklmnopqrstuvwxyz0123",
        f"  {KEY} = 9f8e7d6c5b4a39281706f5e4d3c2b1a0",
        "-----BEGIN " + "PRIVATE KEY-----",
        "token " + "ghp" + "_abcdefghijklmnopqrstuvwxyz0123",
    ],
)
def test_filled_in_secrets_are_detected(text: str) -> None:
    assert any(pattern.search(text) for pattern in SECRET_PATTERNS)


@pytest.mark.parametrize(
    "text",
    [
        f"{KEY}=\nJWT_TTL_MINUTES=15",
        "# JWT_SECRET must come from the environment",
        "jwt_secret: SecretStr | None = None",
    ],
)
def test_placeholders_and_code_are_not_flagged(text: str) -> None:
    assert not any(pattern.search(text) for pattern in SECRET_PATTERNS)
