"""Donation storage.

Defines the storage *interface* (so the persistence layer can later be
swapped for a real database) and a simple in-memory implementation backed by
a dict, which is enough for this demo and for fast, isolated tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import DonationEvent


class DonationStore(ABC):
    """Abstract storage interface for donation events."""

    @abstractmethod
    def add(self, event: DonationEvent) -> None:
        """Persist a new donation event.

        Args:
            event: The validated donation to store.
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
        """Initialise an empty store."""
        # TODO: back the store with an ordered dict keyed by event_id
        raise NotImplementedError

    def add(self, event: DonationEvent) -> None:  # noqa: D102 (see base class)
        raise NotImplementedError

    def get(self, event_id: str) -> DonationEvent | None:  # noqa: D102
        raise NotImplementedError

    def exists(self, event_id: str) -> bool:  # noqa: D102
        raise NotImplementedError

    def list_all(self) -> list[DonationEvent]:  # noqa: D102
        raise NotImplementedError
