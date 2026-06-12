"""Donation storage: an abstract interface (swappable for a real DB later)
and a dict-backed in-memory implementation for the demo and tests.
"""

import threading
from abc import ABC, abstractmethod

from app.models import DonationEvent


class DonationStore(ABC):
    """Abstract storage interface for donation events."""

    @abstractmethod
    def add(self, event: DonationEvent) -> None:
        """Persist an event, overwriting any existing one with the same id.

        Plain writes stay dumb; the 409-on-duplicate rule is the service's
        job via ``add_if_new``.
        """
        raise NotImplementedError

    @abstractmethod
    def add_if_new(self, event: DonationEvent) -> bool:
        """Atomically store ``event`` unless its id already exists.

        The analogue of an INSERT under a unique constraint: check and write
        are one indivisible step, so two concurrent callers can't both win.
        Returns True if stored, False if the id was already present (existing
        event left untouched). ``exists()`` + ``add()`` is NOT equivalent, it
        is check-then-act and races.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, event_id: str) -> DonationEvent | None:
        """Return the event with ``event_id`` or ``None``."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, event_id: str) -> bool:
        """Whether an event with ``event_id`` is stored."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[DonationEvent]:
        """Return all stored events in insertion order."""
        raise NotImplementedError


class InMemoryDonationStore(DonationStore):
    """Dict-backed, non-persistent store. Each test gets a fresh instance."""

    def __init__(self) -> None:
        self._events: dict[str, DonationEvent] = {}
        self._lock = threading.Lock()

    def add(self, event: DonationEvent) -> None:
        self._events[event.event_id] = event

    def add_if_new(self, event: DonationEvent) -> bool:
        with self._lock:
            if event.event_id in self._events:
                return False
            self._events[event.event_id] = event
            return True

    def get(self, event_id: str) -> DonationEvent | None:
        return self._events.get(event_id)

    def exists(self, event_id: str) -> bool:
        return event_id in self._events

    def list_all(self) -> list[DonationEvent]:
        return list(self._events.values())
