"""Integration tests for GET /stats (aggregation over HTTP).

Decimal totals serialise to JSON strings ("30.30"). Exactness survives the
HTTP boundary.
"""

from fastapi.testclient import TestClient

from tests.conftest import post_donation


def test_stats_empty(client: TestClient) -> None:
    """No events -> empty grouping, zero count."""
    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {"by_currency": {}, "total_count": 0}


def test_stats_groups_by_currency(client: TestClient) -> None:
    """Per-currency totals/counts; Decimal totals arrive as strings."""
    post_donation(client, "evt_001", amount="10.00", currency="USD")
    post_donation(client, "evt_002", amount="5.00", currency="EUR")
    post_donation(client, "evt_003", amount="2.50", currency="USD")

    response = client.get("/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3
    assert data["by_currency"]["USD"] == {"total": "12.50", "count": 2}
    assert data["by_currency"]["EUR"] == {"total": "5.00", "count": 1}


def test_stats_decimal_precision_over_http(client: TestClient) -> None:
    """10.10 + 20.20 arrives as exactly "30.30"."""
    post_donation(client, "evt_001", amount="10.10")
    post_donation(client, "evt_002", amount="20.20")

    total = client.get("/stats").json()["by_currency"]["USD"]["total"]

    assert total == "30.30"


def test_stats_counts_only_stored_events(client: TestClient) -> None:
    """Duplicates and rejected currencies never reach stats."""
    post_donation(client, "evt_001", amount="10.00")  # created
    post_donation(client, "evt_001", amount="99.00")  # duplicate -> 409
    post_donation(client, "evt_002", currency="GBP")  # disallowed -> 400

    data = client.get("/stats").json()

    assert data["total_count"] == 1
    assert data["by_currency"]["USD"] == {"total": "10.00", "count": 1}
