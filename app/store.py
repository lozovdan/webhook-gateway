"""Donation storage.

Defines the storage *interface* (so the persistence layer can later be
swapped for a real database) and a simple in-memory implementation backed by
a dict, which is enough for this demo and for fast, isolated tests.
"""

from abc import ABC, abstractmethod

from app.models import DonationEvent


class DonationStore(ABC):
    """Abstract storage interface for donation events."""

    @abstractmethod
    def add(self, event: DonationEvent) -> None:
        """Persist a donation event.

        A duplicate event_id OVERWRITES the stored event (last-write-wins):
        the store is dumb storage; the idempotency rule (409 on duplicate)
        belongs to the service layer, which checks ``exists()`` first.
        """
        raise NotImplementedError

    @abstractmethod
    def add_if_new(self, event: DonationEvent) -> bool:
        """Atomically persist ``event`` unless its event_id is already stored.

        The storage analogue of an INSERT under a unique constraint: the
        existence check and the write are one indivisible operation, safe
        under concurrent callers. Returns ``True`` if the event was stored,
        ``False`` if the event_id already existed (the stored event is left
        untouched).

        The pair ``exists()`` + ``add()`` is NOT a substitute: it is
        check-then-act, and two concurrent callers can both observe
        "absent" and both write.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, event_id: str) -> DonationEvent | None:
        """Return the donation with ``event_id`` or ``None`` if absent."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, event_id: str) -> bool:
        """Return whether a donation with ``event_id`` is already stored."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[DonationEvent]:
        """Return all stored donations (insertion order)."""
        raise NotImplementedError


class InMemoryDonationStore(DonationStore):
    """Dict-backed, non-persistent implementation of :class:`DonationStore`.

    Suitable for the demo and for tests, where each test gets a fresh store.
    """

    def __init__(self) -> None:
        """Initialise an empty store keyed by event_id."""
        self._events: dict[str, DonationEvent] = {}

    def add(self, event: DonationEvent) -> None:  # noqa: D102 (see base class)
        self._events[event.event_id] = event

    def add_if_new(self, event: DonationEvent) -> bool:  # noqa: D102
        raise NotImplementedError

    def get(self, event_id: str) -> DonationEvent | None:  # noqa: D102
        return self._events.get(event_id)

    def exists(self, event_id: str) -> bool:  # noqa: D102
        return event_id in self._events

    def list_all(self) -> list[DonationEvent]:  # noqa: D102
        return list(self._events.values())
