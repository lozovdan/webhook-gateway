"""Business logic for donation processing.

This layer sits between the HTTP routes and the store. It owns the rules that
are *not* HTTP concerns: the currency allowlist, idempotency (a repeated
``event_id`` is not stored twice) and statistics aggregation. The service
knows nothing about HTTP status codes.
"""

from enum import Enum

from app.models import DonationEvent, StatsResponse
from app.store import DonationStore


class ProcessResult(Enum):
    """Outcome of attempting to process a donation event."""

    CREATED = "created"
    DUPLICATE = "duplicate"
    CURRENCY_NOT_ALLOWED = "currency_not_allowed"


class DonationService:
    """Business rules: allowlist, idempotency, aggregation."""

    def __init__(self, store: DonationStore, allowed_currencies: set[str]) -> None:
        """Create the service.

        Args:
            store: Storage backend to read from and write to.
            allowed_currencies: Injected allowlist (service never reads
                config directly — keeps it unit-testable).
        """
        self._store = store
        self._allowed_currencies = allowed_currencies

    def process_donation(self, event: DonationEvent) -> ProcessResult:
        """Apply business rules to a validated event and store it if new.

        Check order: allowlist BEFORE duplicate — an event with a disallowed
        currency gets CURRENCY_NOT_ALLOWED even if its event_id is already
        stored. On DUPLICATE the store is not touched (first write wins).
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
