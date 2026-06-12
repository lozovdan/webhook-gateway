"""Unit tests for app.config (env-driven settings) and the lazy ASGI app.

Isolation: get_settings() has NO cache and monkeypatch reverts env after
each test, so nothing leaks between tests.
"""

import pytest
from fastapi import FastAPI

import app.main
from app.config import (
    DEFAULT_ALLOWED_CURRENCIES,
    DEFAULT_REPLAY_TOLERANCE_SECONDS,
    ENV_ALLOWED_CURRENCIES,
    ENV_REPLAY_TOLERANCE_SECONDS,
    ENV_WEBHOOK_SECRET,
    get_settings,
)


def test_valid_env_builds_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both vars set -> Settings with the secret and the parsed set."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.setenv(ENV_ALLOWED_CURRENCIES, "USD,EUR")

    settings = get_settings()

    assert settings.webhook_secret == "s3cret"
    assert settings.allowed_currencies == frozenset({"USD", "EUR"})


@pytest.mark.parametrize(
    "secret",
    [
        pytest.param(None, id="missing-secret"),
        pytest.param("", id="empty-secret"),
        pytest.param("   ", id="whitespace-secret"),
    ],
)
def test_missing_or_blank_secret_raises(
    monkeypatch: pytest.MonkeyPatch, secret: str | None
) -> None:
    """The service must not start without a real secret. The message names
    the variable to set, that text is the operator's contract."""
    if secret is None:
        monkeypatch.delenv(ENV_WEBHOOK_SECRET, raising=False)
    else:
        monkeypatch.setenv(ENV_WEBHOOK_SECRET, secret)

    with pytest.raises(RuntimeError, match="WEBHOOK_SECRET must be set"):
        get_settings()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("USD,EUR", {"USD", "EUR"}, id="plain"),
        pytest.param(" USD , EUR ", {"USD", "EUR"}, id="spaces-stripped"),
        pytest.param("usd,eur", {"USD", "EUR"}, id="uppercased"),
        pytest.param("USD,,EUR,", {"USD", "EUR"}, id="empty-items-dropped"),
    ],
)
def test_allowed_currencies_parsing(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: set[str]
) -> None:
    """Comma-separated list is normalised (strip + upper) into a set."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.setenv(ENV_ALLOWED_CURRENCIES, raw)

    assert get_settings().allowed_currencies == frozenset(expected)


def test_allowed_currencies_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset ALLOWED_CURRENCIES -> documented default applies."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.delenv(ENV_ALLOWED_CURRENCIES, raising=False)

    assert get_settings().allowed_currencies == DEFAULT_ALLOWED_CURRENCIES


@pytest.mark.parametrize("raw", ["", " , ,"], ids=["empty", "separators-only"])
def test_allowed_currencies_set_but_empty_raises(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Explicitly configured empty allowlist is a misconfiguration, not a default."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.setenv(ENV_ALLOWED_CURRENCIES, raw)

    with pytest.raises(RuntimeError, match="ALLOWED_CURRENCIES is set but empty"):
        get_settings()


# replay tolerance


def test_replay_tolerance_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset REPLAY_TOLERANCE_SECONDS -> documented default applies."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.delenv(ENV_REPLAY_TOLERANCE_SECONDS, raising=False)

    settings = get_settings()

    assert settings.replay_tolerance_seconds == DEFAULT_REPLAY_TOLERANCE_SECONDS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("600", 600, id="plain"),
        pytest.param(" 600 ", 600, id="spaces-stripped"),
        pytest.param("1", 1, id="smallest-valid"),
    ],
)
def test_replay_tolerance_custom_value(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: int
) -> None:
    """A positive integer number of seconds is parsed as-is."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.setenv(ENV_REPLAY_TOLERANCE_SECONDS, raw)

    assert get_settings().replay_tolerance_seconds == expected


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="set-but-empty"),
        pytest.param("abc", id="not-a-number"),
        pytest.param("1.5", id="fractional"),
        pytest.param("0", id="zero-disables-nothing"),
        pytest.param("-5", id="negative"),
    ],
)
def test_replay_tolerance_invalid_raises(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Anything but a positive integer is a misconfiguration: refuse to start.
    '0' is rejected too — disabling replay protection must not be possible
    by accident; there is deliberately no off switch."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.setenv(ENV_REPLAY_TOLERANCE_SECONDS, raw)

    with pytest.raises(
        RuntimeError, match="REPLAY_TOLERANCE_SECONDS must be a positive integer"
    ):
        get_settings()


# --- lazy module-level app (PEP 562) -----------------------------------------


def test_module_level_app_builds_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`uvicorn app.main:app` path: attribute access creates the app."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.delenv(ENV_ALLOWED_CURRENCIES, raising=False)

    application = app.main.app

    assert isinstance(application, FastAPI)
    assert application.title == "Webhook Gateway"  # OpenAPI metadata contract


def test_module_level_app_without_secret_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env -> the app is not silently created with a missing secret."""
    monkeypatch.delenv(ENV_WEBHOOK_SECRET, raising=False)

    with pytest.raises(RuntimeError):
        _ = app.main.app


def test_module_getattr_unknown_attribute_raises() -> None:
    """PEP 562 hook only serves 'app'; anything else is a normal AttributeError
    naming the missing attribute."""
    with pytest.raises(AttributeError, match="no_such_attribute"):
        _ = app.main.no_such_attribute
