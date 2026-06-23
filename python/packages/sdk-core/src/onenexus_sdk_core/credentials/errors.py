"""Credential errors shared by every credential implementation.

Two error types are part of the credential contract, mirroring the
language-agnostic design in the repository ``README.md``:

- :class:`StaleCredentialsError` — recoverable. The held token is stale by local
  expiry rules and this credential cannot refresh it itself. A composing parent
  may catch it and re-mint; a top-level caller must supply a fresh credential.
- :class:`AuthenticationError` — terminal. A refresh or mint attempt was rejected
  by the authentication authority (revoked refresh token, bad client assertion).
  Retrying the same credential source is not expected to recover.
"""

from __future__ import annotations


class StaleCredentialsError(Exception):
    """A held token is stale and this credential cannot refresh it itself."""

    def __init__(self, message: str = "Credentials are stale.") -> None:
        super().__init__(message)


class AuthenticationError(Exception):
    """A refresh or mint attempt was rejected by the authentication authority."""

    def __init__(self, message: str = "Authentication failed.") -> None:
        super().__init__(message)


__all__ = ["AuthenticationError", "StaleCredentialsError"]
