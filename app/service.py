"""Business logic for donation processing.

This layer sits between the HTTP routes and the store. It owns the rules that
are *not* HTTP concerns: idempotency (a repeated ``event_id`` is ignored) and
statistics aggregation. Keeping this logic here lets it be unit-tested
without spinning up the web app.
"""

from __future__ import annotations

from enum import Enum

from app.models import DonationEvent, StatsResponse
from app.store import DonationStore


class ProcessResult(Enum):
    """Outcome of attempting to process a donation event."""

    CREATED = "created"
    DUPLICATE = "duplicate"


class DonationService:
    """Coordinates validation results, persistence and aggregation."""

    def __init__(self, store: DonationStore) -> None:
        """Create the service.

        Args:
            store: The storage backend to read from and write to.
        """
        # TODO: keep a reference to the store
        raise NotImplementedError

    def process_donation(self, event: DonationEvent) -> ProcessResult:
        """Store a donation event idempotently.

        Args:
            event: A validated donation event.

        Returns:
            :attr:`ProcessResult.CREATED` if newly stored, or
            :attr:`ProcessResult.DUPLICATE` if ``event_id`` was already seen.
        """
        raise NotImplementedError

    def get_donation(self, event_id: str) -> DonationEvent | None:
        """Return a single donation by id, or ``None`` if not found."""
        raise NotImplementedError

    def list_donations(self) -> list[DonationEvent]:
        """Return all processed donations."""
        raise NotImplementedError

    def compute_stats(self) -> StatsResponse:
        """Aggregate stored donations into per-currency totals and counts."""
        raise NotImplementedError
