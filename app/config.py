"""Application configuration.

All runtime settings are sourced from environment variables so that no
secrets are hard-coded. The shared HMAC secret and the currency allowlist
live here and are injected wherever they are needed (signature verification,
payload validation).
"""

import os
from dataclasses import dataclass

# Environment variable names (kept as constants to avoid typos across modules).
ENV_WEBHOOK_SECRET = "WEBHOOK_SECRET"
ENV_ALLOWED_CURRENCIES = "ALLOWED_CURRENCIES"
ENV_REPLAY_TOLERANCE_SECONDS = "REPLAY_TOLERANCE_SECONDS"

# Fallback allowlist used when ALLOWED_CURRENCIES is not provided.
DEFAULT_ALLOWED_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR", "CZK"})

# Fallback replay window (Stripe's default) when REPLAY_TOLERANCE_SECONDS
# is not provided.
DEFAULT_REPLAY_TOLERANCE_SECONDS: int = 300


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration for the gateway.

    Attributes:
        webhook_secret: Shared secret used to verify the ``X-Signature`` HMAC.
        allowed_currencies: Uppercase ISO currency codes accepted in payloads.
        replay_tolerance_seconds: Maximum allowed |now - event.timestamp|;
            events outside this symmetric window are rejected as replays.
    """

    webhook_secret: str
    allowed_currencies: frozenset[str]
    replay_tolerance_seconds: int = DEFAULT_REPLAY_TOLERANCE_SECONDS


def get_settings() -> Settings:
    """Build a :class:`Settings` instance from the process environment.

    Reads ``WEBHOOK_SECRET`` (required, non-empty) and ``ALLOWED_CURRENCIES``
    (optional, comma-separated, normalised with strip+upper; unset falls back
    to :data:`DEFAULT_ALLOWED_CURRENCIES`). No caching: env is read on every
    call — it runs once at app startup, and tests stay isolated for free.

    Raises:
        RuntimeError: If the secret is missing/empty, or if
            ``ALLOWED_CURRENCIES`` is set but parses to an empty set.
    """
    secret = os.environ.get(ENV_WEBHOOK_SECRET, "").strip()
    if not secret:
        raise RuntimeError(f"{ENV_WEBHOOK_SECRET} must be set and non-empty")

    raw = os.environ.get(ENV_ALLOWED_CURRENCIES)
    if raw is None:
        currencies = DEFAULT_ALLOWED_CURRENCIES
    else:
        currencies = frozenset(
            item.strip().upper() for item in raw.split(",") if item.strip()
        )
        if not currencies:
            raise RuntimeError(f"{ENV_ALLOWED_CURRENCIES} is set but empty")

    return Settings(webhook_secret=secret, allowed_currencies=currencies)
