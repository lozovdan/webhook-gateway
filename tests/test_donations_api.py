"""Integration tests for GET /donations, GET /donations/{event_id}, /health.

Red phase: route bodies are NotImplementedError stubs.
Decision locked: Decimal amounts serialise to JSON STRINGS ("10.00").
"""

from fastapi.testclient import TestClient

from tests.conftest import post_donation


def test_list_donations_empty(client: TestClient) -> None:
    """No events ingested -> 200 with an empty list."""
    response = client.get("/donations")

    assert response.status_code == 200
    assert response.json() == []


def test_list_donations_after_posts_in_order(client: TestClient) -> None:
    """All ingested events are listed in insertion order."""
    for i in range(1, 4):
        assert post_donation(client, f"evt_{i:03d}").status_code == 200

    response = client.get("/donations")

    assert response.status_code == 200
    listed = response.json()
    assert [e["event_id"] for e in listed] == ["evt_001", "evt_002", "evt_003"]
    assert listed[0]["amount"] == "10.00"  # Decimal -> JSON string


def test_get_donation_existing_returns_event(client: TestClient) -> None:
    """Known event_id -> 200 with the stored event."""
    post_donation(client, "evt_001")

    response = client.get("/donations/evt_001")

    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == "evt_001"
    assert data["donor"] == "Alice Donor"
    assert data["amount"] == "10.00"
    assert data["currency"] == "USD"


def test_get_donation_missing_returns_404(client: TestClient) -> None:
    """Unknown event_id -> 404."""
    assert client.get("/donations/evt_missing").status_code == 404


def test_health_returns_ok(client: TestClient) -> None:
    """Liveness check."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
