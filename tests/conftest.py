"""Shared fixtures and helpers for the API-level tests.

Isolation: ``create_app()`` builds a NEW store inside every app instance and
the ``app`` fixture is function-scoped — each test gets fresh state.

Determinism: the test app gets an injected clock frozen at ``FIXED_NOW`` and
the default payload timestamp IS ``FIXED_NOW`` — every event is "fresh"
(age 0) unless a test overrides the timestamp on purpose. No test depends
on the real wall clock.

Helpers are plain functions (importable as ``from tests.conftest import ...``):
``sign`` produces a valid X-Signature for exact bytes under the test secret;
``post_donation`` posts a correctly signed valid event.
"""

import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings
from app.main import create_app
from app.signature import generate_signature

TEST_SECRET = "test-secret"
TEST_ALLOWED_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR"})
TEST_REPLAY_TOLERANCE_SECONDS = 300
WEBHOOK_PATH = "/webhooks/donation"

# The single instant the test app's injected clock always returns.
FIXED_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def make_payload(event_id: str = "evt_001", **overrides: object) -> dict[str, object]:
    """Valid donation payload dict (amount as a string) with overrides."""
    payload: dict[str, object] = {
        "event_id": event_id,
        "donor": "Alice Donor",
        "amount": "10.00",
        "currency": "USD",
        "timestamp": FIXED_NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


def payload_bytes(event_id: str = "evt_001", **overrides: object) -> bytes:
    """JSON-encoded valid payload."""
    return json.dumps(make_payload(event_id, **overrides)).encode()


def sign(body: bytes) -> str:
    """Valid X-Signature value for these exact bytes under the test secret."""
    return generate_signature(body, TEST_SECRET)


def signed_headers(body: bytes) -> dict[str, str]:
    """Headers carrying a valid signature for ``body``."""
    return {"X-Signature": sign(body), "Content-Type": "application/json"}


def post_donation(
    client: TestClient, event_id: str = "evt_001", **overrides: object
) -> Response:
    """POST a correctly signed donation built from the valid payload."""
    body = payload_bytes(event_id, **overrides)
    return client.post(WEBHOOK_PATH, content=body, headers=signed_headers(body))


@pytest.fixture()
def app() -> FastAPI:
    """Fresh app (and store inside it) per test, with time frozen at FIXED_NOW."""
    settings = Settings(
        webhook_secret=TEST_SECRET,
        allowed_currencies=TEST_ALLOWED_CURRENCIES,
        replay_tolerance_seconds=TEST_REPLAY_TOLERANCE_SECONDS,
    )
    return create_app(settings=settings, clock=lambda: FIXED_NOW)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """TestClient bound to the per-test app."""
    return TestClient(app)
