"""Integration tests for POST /webhooks/donation.

Red phase: the dependency and route bodies are NotImplementedError stubs.

Decisions locked here:
    - The HMAC is verified over the RAW body BEFORE payload parsing:
      bad signature + bad payload -> 401, never 400.
    - Validation errors map to 400 (manual parsing), not FastAPI's 422.
    - ProcessResult mapping: CREATED->200, DUPLICATE->409,
      CURRENCY_NOT_ALLOWED->400, STALE_TIMESTAMP->400.
    - A replayed (stale) event is 400, NOT 401: its signature IS valid, so
      it is a payload rejection, not an authentication failure.
"""

import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    FIXED_NOW,
    TEST_REPLAY_TOLERANCE_SECONDS,
    WEBHOOK_PATH,
    make_payload,
    payload_bytes,
    post_donation,
    sign,
    signed_headers,
)


def test_valid_event_returns_200_created(client: TestClient) -> None:
    """Happy path: valid payload + valid signature -> 200 with ack body."""
    response = post_donation(client, "evt_001")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert data["event_id"] == "evt_001"


def test_duplicate_event_id_returns_409(client: TestClient) -> None:
    """Same event_id twice (both signed) -> second answer is 409."""
    assert post_donation(client, "evt_001").status_code == 200

    response = post_donation(client, "evt_001", donor="Bob Donor")

    assert response.status_code == 409


def test_disallowed_currency_returns_400(client: TestClient) -> None:
    """Well-formed but disallowed currency -> 400 (business rejection)."""
    response = post_donation(client, "evt_001", currency="GBP")

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("overrides", "drop"),
    [
        pytest.param({"amount": "-5.00"}, None, id="negative-amount"),
        pytest.param({"currency": "usd"}, None, id="bad-currency-format"),
        pytest.param({}, "donor", id="missing-required-field"),
        pytest.param(
            {"timestamp": "2026-06-09T12:00:00"}, None, id="naive-timestamp"
        ),
    ],
)
def test_invalid_payload_with_valid_signature_returns_400(
    client: TestClient, overrides: dict[str, object], drop: str | None
) -> None:
    """Validation failures -> 400, not 422; signature is valid to isolate
    the parsing path from the auth path."""
    payload = make_payload("evt_001", **overrides)
    if drop is not None:
        del payload[drop]
    body = json.dumps(payload).encode()

    response = client.post(WEBHOOK_PATH, content=body, headers=signed_headers(body))

    assert response.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b'{"event_id": "evt_001", "donor":', id="truncated-json"),
        pytest.param(b"", id="empty-body"),
    ],
)
def test_broken_json_with_valid_signature_returns_400(
    client: TestClient, body: bytes
) -> None:
    """Syntactically broken/empty body, correctly signed -> 400.

    An HMAC over b"" is mathematically valid (see test_signature), so the
    auth step passes and the failure MUST come from parsing, not 401.
    """
    response = client.post(WEBHOOK_PATH, content=body, headers=signed_headers(body))

    assert response.status_code == 400


@pytest.mark.parametrize(
    "offset_seconds",
    [
        pytest.param(-(TEST_REPLAY_TOLERANCE_SECONDS + 1), id="too-old"),
        pytest.param(TEST_REPLAY_TOLERANCE_SECONDS + 1, id="too-far-in-future"),
    ],
)
def test_timestamp_outside_tolerance_returns_400(
    client: TestClient, offset_seconds: int
) -> None:
    """Correctly signed event outside the replay window -> 400.

    Not 401: the signature is cryptographically valid, so this is a payload
    rejection. The app clock is frozen at FIXED_NOW (see conftest), so the
    window is checked deterministically."""
    stamp = (FIXED_NOW + timedelta(seconds=offset_seconds)).isoformat()
    body = payload_bytes("evt_001", timestamp=stamp)

    response = client.post(WEBHOOK_PATH, content=body, headers=signed_headers(body))

    assert response.status_code == 400


def test_timestamp_on_tolerance_boundary_returns_200(client: TestClient) -> None:
    """An event exactly tolerance old is still accepted (inclusive boundary)."""
    stamp = (FIXED_NOW - timedelta(seconds=TEST_REPLAY_TOLERANCE_SECONDS)).isoformat()
    body = payload_bytes("evt_001", timestamp=stamp)

    response = client.post(WEBHOOK_PATH, content=body, headers=signed_headers(body))

    assert response.status_code == 200


def test_wrong_signature_returns_401(client: TestClient) -> None:
    """Valid payload, garbage signature -> 401."""
    body = payload_bytes("evt_001")

    response = client.post(
        WEBHOOK_PATH,
        content=body,
        headers={"X-Signature": "0" * 64, "Content-Type": "application/json"},
    )

    assert response.status_code == 401


def test_missing_signature_header_returns_401(client: TestClient) -> None:
    """No X-Signature header at all -> 401."""
    response = client.post(
        WEBHOOK_PATH,
        content=payload_bytes("evt_001"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


def test_signature_for_different_body_returns_401(client: TestClient) -> None:
    """A signature taken from OTHER bytes (tampered payload) -> 401."""
    original = payload_bytes("evt_001")
    tampered = payload_bytes("evt_001", amount="999.00")

    response = client.post(
        WEBHOOK_PATH,
        content=tampered,
        headers={"X-Signature": sign(original), "Content-Type": "application/json"},
    )

    assert response.status_code == 401


def test_bad_signature_wins_over_bad_payload(client: TestClient) -> None:
    """Order: 401 before 400 — invalid payload with bad signature is 401."""
    body = b'{"amount": "-5.00"}'  # invalid payload too

    response = client.post(
        WEBHOOK_PATH,
        content=body,
        headers={"X-Signature": "0" * 64, "Content-Type": "application/json"},
    )

    assert response.status_code == 401


def test_signature_is_verified_over_raw_bytes(client: TestClient) -> None:
    """Non-standard JSON formatting passes when signed over the SAME bytes —
    verification uses the raw body, not a re-serialised payload."""
    body = (
        b'{  "event_id": "evt_raw",\n'
        b'   "donor": "Alice Donor",   "amount": "10.00",\n'
        b'   "currency": "USD",  "timestamp": "2026-06-09T12:00:00Z"  }'
    )

    response = client.post(WEBHOOK_PATH, content=body, headers=signed_headers(body))

    assert response.status_code == 200
    assert response.json()["event_id"] == "evt_raw"
