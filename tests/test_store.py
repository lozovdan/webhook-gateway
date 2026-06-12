"""Unit tests for app.store (InMemoryDonationStore).

Red phase: the method bodies are NotImplementedError stubs; every test below
must fail with NotImplementedError until the green phase fills them in.

Contract decisions locked here:
    - ``add()`` with a duplicate event_id simply OVERWRITES (dict
      semantics): plain writes stay dumb.
    - ``add_if_new()`` is the ATOMIC insert (first write wins, returns
      whether it stored), the storage analogue of a unique-constraint
      INSERT. Atomicity lives in the store because only the store can make
      check+write indivisible; the business decision "duplicate -> 409"
      still lives in the service.
"""

from typing import Any

import pytest

from app.models import DonationEvent
from app.store import InMemoryDonationStore


def make_event(event_id: str = "evt_001", **overrides: object) -> DonationEvent:
    """Build a valid DonationEvent with optional field overrides."""
    payload: dict[str, Any] = {
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
    """Fresh store per test — no state leaks between tests."""
    return InMemoryDonationStore()


def test_add_then_get_returns_stored_event(store: InMemoryDonationStore) -> None:
    """An added event is retrievable by its event_id with identical data."""
    event = make_event("evt_001")
    store.add(event)

    assert store.get("evt_001") == event


def test_get_missing_event_id_returns_none(store: InMemoryDonationStore) -> None:
    """get() returns None for an unknown event_id, never raises."""
    assert store.get("evt_missing") is None


@pytest.mark.parametrize(
    ("event_id", "expected"),
    [
        pytest.param("evt_001", True, id="added-id-exists"),
        pytest.param("evt_missing", False, id="absent-id-does-not-exist"),
    ],
)
def test_exists(store: InMemoryDonationStore, event_id: str, expected: bool) -> None:
    """exists() is True only for stored event_ids (idempotency probe)."""
    store.add(make_event("evt_001"))

    assert store.exists(event_id) is expected


def test_list_all_on_empty_store_returns_empty_list(
    store: InMemoryDonationStore,
) -> None:
    """A fresh store lists no events."""
    assert store.list_all() == []


def test_list_all_returns_all_events_in_insertion_order(
    store: InMemoryDonationStore,
) -> None:
    """list_all() returns every added event, preserving insertion order."""
    events = [make_event(f"evt_{i:03d}") for i in range(1, 4)]
    for event in events:
        store.add(event)

    listed = store.list_all()

    assert len(listed) == 3
    assert [e.event_id for e in listed] == ["evt_001", "evt_002", "evt_003"]


def test_add_duplicate_event_id_overwrites(store: InMemoryDonationStore) -> None:
    """Duplicate event_id overwrites (last-write-wins), no error, no growth.

    The store does NOT enforce idempotency: deciding "this is a duplicate"
    (HTTP 409) is the service's job via exists() before add().
    """
    store.add(make_event("evt_001", donor="Alice Donor"))
    store.add(make_event("evt_001", donor="Bob Donor"))

    stored = store.get("evt_001")
    assert stored is not None
    assert stored.donor == "Bob Donor"
    assert len(store.list_all()) == 1


def test_add_if_new_stores_and_returns_true(store: InMemoryDonationStore) -> None:
    """A new event_id is stored and reported as stored."""
    event = make_event("evt_001")

    assert store.add_if_new(event) is True
    assert store.get("evt_001") == event


def test_add_if_new_duplicate_returns_false_and_keeps_first(
    store: InMemoryDonationStore,
) -> None:
    """A known event_id is NOT overwritten (first write wins) and reports False"""
    assert store.add_if_new(make_event("evt_001", donor="Alice Donor")) is True

    assert store.add_if_new(make_event("evt_001", donor="Bob Donor")) is False
    stored = store.get("evt_001")
    assert stored is not None
    assert stored.donor == "Alice Donor"
    assert len(store.list_all()) == 1


def test_isolation_part1_populates_store(store: InMemoryDonationStore) -> None:
    """First half of the isolation pair: leave state in this test's store."""
    store.add(make_event("evt_leak"))

    assert store.exists("evt_leak") is True


def test_isolation_part2_gets_fresh_store(store: InMemoryDonationStore) -> None:
    """Second half: the fixture yields a clean store, part1's state is gone."""
    assert store.exists("evt_leak") is False
    assert store.list_all() == []
