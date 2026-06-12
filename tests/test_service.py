"""Unit tests for app.service (DonationService).

Red phase: DonationService method bodies are NotImplementedError stubs;
every test below must fail until the green phase fills them in.

Decisions locked here:
    - Check order in process_donation: replay window BEFORE allowlist
      BEFORE duplicate — a stale event reports STALE_TIMESTAMP even when
      its currency is disallowed or its event_id is already stored.
    - Replay window is SYMMETRIC and the boundary is INCLUSIVE:
      |now - timestamp| <= tolerance is accepted, strictly greater is
      rejected. Events from the future beyond the window are as
      suspicious as old ones (clock skew within the window is fine).
    - The clock is INJECTED (no real time in tests); freshness compares
      instants, not wall-clock strings — the same moment in another
      timezone is fresh.
    - On DUPLICATE the store is not touched (first write wins at the
      service level; the store itself stays dumb last-write-wins).
    - Stats are grouped BY currency; totals use exact Decimal arithmetic.
"""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from app.models import DonationEvent
from app.service import DonationService, ProcessResult
from app.store import InMemoryDonationStore

# Test allowlist is injected, independent of app config.
ALLOWED_CURRENCIES: set[str] = {"USD", "EUR"}

# Frozen "now" returned by the injected clock; the default event timestamp
# equals it, so events are fresh (age 0) unless a test overrides it.
FIXED_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
TOLERANCE = timedelta(seconds=300)


def make_event(event_id: str = "evt_001", **overrides: object) -> DonationEvent:
    """Build a valid DonationEvent with optional field overrides."""
    payload: dict[str, Any] = {
        "event_id": event_id,
        "donor": "Alice Donor",
        "amount": "10.00",
        "currency": "USD",
        "timestamp": FIXED_NOW,
    }
    payload.update(overrides)
    return DonationEvent(**payload)


@pytest.fixture()
def store() -> InMemoryDonationStore:
    """Fresh store per test."""
    return InMemoryDonationStore()


@pytest.fixture()
def service(store: InMemoryDonationStore) -> DonationService:
    """Service wired to the fresh store, test allowlist and a frozen clock."""
    return DonationService(
        store=store,
        allowed_currencies=ALLOWED_CURRENCIES,
        replay_tolerance=TOLERANCE,
        clock=lambda: FIXED_NOW,
    )


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


# replay protection


@pytest.mark.parametrize(
    "offset",
    [
        pytest.param(timedelta(0), id="exactly-now"),
        pytest.param(-TOLERANCE, id="oldest-allowed-inclusive-boundary"),
        pytest.param(TOLERANCE, id="newest-allowed-inclusive-boundary"),
        pytest.param(-TOLERANCE + timedelta(seconds=1), id="just-inside-past"),
    ],
)
def test_process_event_within_tolerance_is_created(
    service: DonationService, store: InMemoryDonationStore, offset: timedelta
) -> None:
    """|now - timestamp| <= tolerance -> CREATED; the boundary itself passes."""
    result = service.process_donation(
        make_event("evt_001", timestamp=FIXED_NOW + offset)
    )

    assert result is ProcessResult.CREATED
    assert store.exists("evt_001") is True


@pytest.mark.parametrize(
    "offset",
    [
        pytest.param(-TOLERANCE - timedelta(seconds=1), id="too-old"),
        pytest.param(TOLERANCE + timedelta(seconds=1), id="too-far-in-future"),
        pytest.param(
            -TOLERANCE - timedelta(microseconds=1), id="past-boundary-by-one-us"
        ),
    ],
)
def test_process_event_outside_tolerance_is_stale_and_not_stored(
    service: DonationService, store: InMemoryDonationStore, offset: timedelta
) -> None:
    """|now - timestamp| > tolerance -> STALE_TIMESTAMP, nothing stored."""
    result = service.process_donation(
        make_event("evt_001", timestamp=FIXED_NOW + offset)
    )

    assert result is ProcessResult.STALE_TIMESTAMP
    assert store.list_all() == []


def test_stale_wins_over_disallowed_currency(
    service: DonationService, store: InMemoryDonationStore
) -> None:
    """Check order: replay window BEFORE allowlist — a stale event with a
    disallowed currency reports STALE_TIMESTAMP, not CURRENCY_NOT_ALLOWED."""
    stale = FIXED_NOW - TOLERANCE - timedelta(seconds=1)

    result = service.process_donation(
        make_event("evt_001", currency="GBP", timestamp=stale)
    )

    assert result is ProcessResult.STALE_TIMESTAMP
    assert store.list_all() == []


def test_stale_wins_over_duplicate(
    service: DonationService, store: InMemoryDonationStore
) -> None:
    """Check order: replay window BEFORE exists — replaying a KNOWN event_id
    with a stale timestamp is STALE_TIMESTAMP, not DUPLICATE (that is the
    actual replay-attack shape)."""
    service.process_donation(make_event("evt_001"))
    stale = FIXED_NOW - TOLERANCE - timedelta(seconds=1)

    result = service.process_donation(make_event("evt_001", timestamp=stale))

    assert result is ProcessResult.STALE_TIMESTAMP
    assert len(store.list_all()) == 1


def test_replay_check_compares_instants_not_wall_clock(
    service: DonationService,
) -> None:
    """FIXED_NOW expressed in UTC+5 is the SAME instant -> fresh, CREATED."""
    same_instant_elsewhere = FIXED_NOW.astimezone(timezone(timedelta(hours=5)))

    result = service.process_donation(
        make_event("evt_001", timestamp=same_instant_elsewhere)
    )

    assert result is ProcessResult.CREATED


def test_default_clock_uses_real_time(store: InMemoryDonationStore) -> None:
    """Without an injected clock the service reads real UTC time — an event
    stamped datetime.now(UTC) is fresh. Guards the production default."""
    service = DonationService(
        store=store,
        allowed_currencies=ALLOWED_CURRENCIES,
        replay_tolerance=TOLERANCE,
    )

    result = service.process_donation(
        make_event("evt_001", timestamp=datetime.now(UTC))
    )

    assert result is ProcessResult.CREATED


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
