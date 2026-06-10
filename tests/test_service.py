"""Unit tests for app.service (DonationService).

Red phase: DonationService method bodies are NotImplementedError stubs;
every test below must fail until the green phase fills them in.

Decisions locked here:
    - Check order in process_donation: allowlist BEFORE duplicate — a
      disallowed currency wins even when event_id is already stored.
    - On DUPLICATE the store is not touched (first write wins at the
      service level; the store itself stays dumb last-write-wins).
    - Stats are grouped BY currency; totals use exact Decimal arithmetic.
"""

from decimal import Decimal

import pytest

from app.models import DonationEvent
from app.service import DonationService, ProcessResult
from app.store import InMemoryDonationStore

# Test allowlist is injected, independent of app config.
ALLOWED_CURRENCIES: set[str] = {"USD", "EUR"}


def make_event(event_id: str = "evt_001", **overrides: object) -> DonationEvent:
    """Build a valid DonationEvent with optional field overrides."""
    payload: dict[str, object] = {
        "event_id": event_id,
        "donor": "Alice Donor",
        "amount": "10.00",
        "currency": "USD",
        "timestamp": "2026-06-09T12:00:00Z",
    }
    payload.update(overrides)
    return DonationEvent(**payload)


@pytest.fixture()
def store() -> InMemoryDonationStore:
    """Fresh store per test."""
    return InMemoryDonationStore()


@pytest.fixture()
def service(store: InMemoryDonationStore) -> DonationService:
    """Service wired to the fresh store and the test allowlist."""
    return DonationService(store=store, allowed_currencies=ALLOWED_CURRENCIES)


# process_donation


@pytest.mark.parametrize("currency", ["USD", "EUR"], ids=["usd", "eur"])
def test_process_new_event_is_created_and_stored(
    service: DonationService, store: InMemoryDonationStore, currency: str
) -> None:
    """A new event with an allowed currency is CREATED and lands in the store."""
    result = service.process_donation(make_event("evt_001", currency=currency))

    assert result is ProcessResult.CREATED
    assert store.exists("evt_001") is True


def test_process_duplicate_event_id_is_duplicate_and_not_stored(
    service: DonationService, store: InMemoryDonationStore
) -> None:
    """Second event with the same event_id -> DUPLICATE; store keeps the first."""
    assert service.process_donation(make_event("evt_001")) is ProcessResult.CREATED

    result = service.process_donation(make_event("evt_001", donor="Bob Donor"))

    assert result is ProcessResult.DUPLICATE
    assert len(store.list_all()) == 1
    stored = store.get("evt_001")
    assert stored is not None
    assert stored.donor == "Alice Donor"  # first write wins, no overwrite


def test_process_disallowed_currency_is_rejected_and_not_stored(
    service: DonationService, store: InMemoryDonationStore
) -> None:
    """Currency outside the allowlist -> CURRENCY_NOT_ALLOWED, nothing stored."""
    result = service.process_donation(make_event("evt_001", currency="GBP"))

    assert result is ProcessResult.CURRENCY_NOT_ALLOWED
    assert store.list_all() == []


def test_process_disallowed_currency_wins_over_duplicate(
    service: DonationService, store: InMemoryDonationStore
) -> None:
    """Check order: allowlist BEFORE exists — bad currency on a known
    event_id reports CURRENCY_NOT_ALLOWED, not DUPLICATE."""
    service.process_donation(make_event("evt_001"))

    result = service.process_donation(make_event("evt_001", currency="GBP"))

    assert result is ProcessResult.CURRENCY_NOT_ALLOWED
    assert len(store.list_all()) == 1


# get / list


def test_get_donation_returns_event_or_none(service: DonationService) -> None:
    """get_donation proxies the store: event for a known id, None otherwise."""
    event = make_event("evt_001")
    service.process_donation(event)

    assert service.get_donation("evt_001") == event
    assert service.get_donation("evt_missing") is None


def test_list_donations_empty(service: DonationService) -> None:
    """No processed events -> empty list."""
    assert service.list_donations() == []


def test_list_donations_returns_created_events_in_order(
    service: DonationService,
) -> None:
    """All CREATED events are listed in insertion order."""
    for i in range(1, 4):
        service.process_donation(make_event(f"evt_{i:03d}"))

    listed = service.list_donations()

    assert [e.event_id for e in listed] == ["evt_001", "evt_002", "evt_003"]


# compute_stats


def test_compute_stats_empty_store(service: DonationService) -> None:
    """Empty store -> no currencies, zero total_count."""
    stats = service.compute_stats()

    assert stats.by_currency == {}
    assert stats.total_count == 0


def test_compute_stats_single_currency_sums_amounts(
    service: DonationService,
) -> None:
    """Same-currency events are summed; count matches."""
    service.process_donation(make_event("evt_001", amount="10.00"))
    service.process_donation(make_event("evt_002", amount="5.50"))

    stats = service.compute_stats()

    assert stats.total_count == 2
    assert stats.by_currency["USD"].total == Decimal("15.50")
    assert stats.by_currency["USD"].count == 2


def test_compute_stats_groups_by_currency(service: DonationService) -> None:
    """Currencies aggregate separately and are never summed together."""
    service.process_donation(make_event("evt_001", amount="10.00", currency="USD"))
    # int amount exercises the str-and-int contract through the full path
    service.process_donation(make_event("evt_002", amount=5, currency="EUR"))
    service.process_donation(make_event("evt_003", amount="2.50", currency="USD"))

    stats = service.compute_stats()

    assert set(stats.by_currency) == {"USD", "EUR"}
    assert stats.by_currency["USD"].total == Decimal("12.50")
    assert stats.by_currency["USD"].count == 2
    assert stats.by_currency["EUR"].total == Decimal("5.00")
    assert stats.by_currency["EUR"].count == 1
    assert stats.total_count == 3
    # invariant: total_count counts events, consistent with the grouping
    assert stats.total_count == sum(c.count for c in stats.by_currency.values())


def test_compute_stats_counts_only_created_events(service: DonationService) -> None:
    """DUPLICATE and CURRENCY_NOT_ALLOWED outcomes never reach stats."""
    service.process_donation(make_event("evt_001", amount="10.00"))
    service.process_donation(make_event("evt_001", amount="99.00"))  # duplicate
    service.process_donation(make_event("evt_002", currency="GBP"))  # disallowed

    stats = service.compute_stats()

    assert stats.total_count == 1
    assert stats.by_currency["USD"].total == Decimal("10.00")
    assert stats.by_currency["USD"].count == 1


def test_compute_stats_uses_exact_decimal_addition(
    service: DonationService,
) -> None:
    """10.10 + 20.20 must be exactly Decimal('30.30') — float arithmetic
    would yield 30.299999999999997 and fail this equality."""
    service.process_donation(make_event("evt_001", amount="10.10"))
    service.process_donation(make_event("evt_002", amount="20.20"))

    total = service.compute_stats().by_currency["USD"].total

    assert isinstance(total, Decimal)
    assert total == Decimal("30.30")
