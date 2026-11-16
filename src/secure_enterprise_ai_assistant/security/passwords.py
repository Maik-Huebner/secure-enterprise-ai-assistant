"""Password hashing with Argon2id (OWASP recommendation)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12

# argon2-cffi defaults follow RFC 9106 (Argon2id, 64 MiB memory, 3 iterations).
_HASHER = PasswordHasher()
# Verified for unknown users so that the response time does not reveal valid user names.
_DUMMY_HASH = _HASHER.hash("timing-equalizer-not-a-real-password")


class WeakPasswordError(ValueError):
    """Raised when a new password does not meet the minimum policy."""


def hash_password(password: str) -> str:
    """Return an Argon2id hash for a new password."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."
        )
    return _HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Check a password in roughly constant time, also for unknown users (``None``)."""
    try:
        return _HASHER.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when stored parameters are weaker than the current defaults."""
    return _HASHER.check_needs_rehash(password_hash)
