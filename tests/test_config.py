"""Unit tests for app.config (env-driven settings) and the lazy ASGI app.

Isolation: get_settings() has NO cache and monkeypatch reverts env after
each test, so nothing leaks between tests.
"""

import pytest
from fastapi import FastAPI

import app.main
from app.config import (
    DEFAULT_ALLOWED_CURRENCIES,
    ENV_ALLOWED_CURRENCIES,
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
    """The service must not start without a real secret."""
    if secret is None:
        monkeypatch.delenv(ENV_WEBHOOK_SECRET, raising=False)
    else:
        monkeypatch.setenv(ENV_WEBHOOK_SECRET, secret)

    with pytest.raises(RuntimeError):
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

    with pytest.raises(RuntimeError):
        get_settings()


# --- lazy module-level app (PEP 562) -----------------------------------------


def test_module_level_app_builds_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`uvicorn app.main:app` path: attribute access creates the app."""
    monkeypatch.setenv(ENV_WEBHOOK_SECRET, "s3cret")
    monkeypatch.delenv(ENV_ALLOWED_CURRENCIES, raising=False)

    assert isinstance(app.main.app, FastAPI)


def test_module_level_app_without_secret_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env -> the app is not silently created with a missing secret."""
    monkeypatch.delenv(ENV_WEBHOOK_SECRET, raising=False)

    with pytest.raises(RuntimeError):
        _ = app.main.app


def test_module_getattr_unknown_attribute_raises() -> None:
    """PEP 562 hook only serves 'app'; anything else is a normal AttributeError."""
    with pytest.raises(AttributeError):
        _ = app.main.no_such_attribute
