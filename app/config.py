"""Application configuration.

All runtime settings are sourced from environment variables so that no
secrets are hard-coded. The shared HMAC secret and the currency allowlist
live here and are injected wherever they are needed (signature verification,
payload validation).
"""

from __future__ import annotations

from dataclasses import dataclass

# Environment variable names (kept as constants to avoid typos across modules).
ENV_WEBHOOK_SECRET = "WEBHOOK_SECRET"
ENV_ALLOWED_CURRENCIES = "ALLOWED_CURRENCIES"

# Fallback allowlist used when ALLOWED_CURRENCIES is not provided.
DEFAULT_ALLOWED_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR", "CZK"})


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration for the gateway.

    Attributes:
        webhook_secret: Shared secret used to verify the ``X-Signature`` HMAC.
        allowed_currencies: Uppercase ISO currency codes accepted in payloads.
    """

    webhook_secret: str
    allowed_currencies: frozenset[str]


def get_settings() -> Settings:
    """Build a :class:`Settings` instance from the process environment.

    Reads ``WEBHOOK_SECRET`` (required) and ``ALLOWED_CURRENCIES`` (optional,
    comma-separated; falls back to :data:`DEFAULT_ALLOWED_CURRENCIES`).

    Returns:
        A populated, immutable :class:`Settings`.

    Raises:
        RuntimeError: If a required variable is missing.
    """
    raise NotImplementedError
