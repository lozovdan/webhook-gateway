"""Runtime configuration, sourced entirely from environment variables so no
secrets are hard-coded.
"""

import os
from dataclasses import dataclass

# Env var names as constants to avoid typos across modules.
ENV_WEBHOOK_SECRET = "WEBHOOK_SECRET"
ENV_ALLOWED_CURRENCIES = "ALLOWED_CURRENCIES"
ENV_REPLAY_TOLERANCE_SECONDS = "REPLAY_TOLERANCE_SECONDS"

DEFAULT_ALLOWED_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR", "CZK"})
DEFAULT_REPLAY_TOLERANCE_SECONDS: int = 300


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration for the gateway."""

    webhook_secret: str
    allowed_currencies: frozenset[str]
    replay_tolerance_seconds: int = DEFAULT_REPLAY_TOLERANCE_SECONDS


def get_settings() -> Settings:
    """Build :class:`Settings` from the environment.

    Not cached: env is read on every call. It runs once at startup, and tests
    stay isolated for free.

    Raises:
        RuntimeError: if the secret is missing/empty, ``ALLOWED_CURRENCIES``
            is set but parses to empty, or ``REPLAY_TOLERANCE_SECONDS`` is set
            but is not a positive integer.
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

    raw_tolerance = os.environ.get(ENV_REPLAY_TOLERANCE_SECONDS)
    if raw_tolerance is None:
        tolerance = DEFAULT_REPLAY_TOLERANCE_SECONDS
    else:
        error = (
            f"{ENV_REPLAY_TOLERANCE_SECONDS} must be a positive integer, "
            f"got {raw_tolerance!r}"
        )
        try:
            tolerance = int(raw_tolerance)
        except ValueError as exc:
            raise RuntimeError(error) from exc
        if tolerance <= 0:
            raise RuntimeError(error)

    return Settings(
        webhook_secret=secret,
        allowed_currencies=currencies,
        replay_tolerance_seconds=tolerance,
    )
