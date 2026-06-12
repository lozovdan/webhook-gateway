"""Business logic for donation processing: replay window, currency allowlist,
idempotency and stats aggregation. Knows nothing about HTTP.

Time is read through an injected ``clock`` so time-dependent rules are
deterministic in tests.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.models import CurrencyTotal, DonationEvent, StatsResponse
from app.store import DonationStore


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ProcessResult(Enum):
    """Outcome of attempting to process a donation event."""

    CREATED = "created"
    DUPLICATE = "duplicate"
    CURRENCY_NOT_ALLOWED = "currency_not_allowed"
    STALE_TIMESTAMP = "stale_timestamp"


class DonationService:
    """Business rules: allowlist, idempotency, aggregation."""

    def __init__(
        self,
        store: DonationStore,
        allowed_currencies: set[str],
        *,
        replay_tolerance: timedelta,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        # allowlist and tolerance are injected, not read from config here, so
        # the service stays unit-testable. clock defaults to real UTC time;
        # tests inject a frozen one for determinism.
        self._store = store
        self._allowed_currencies = allowed_currencies
        self._replay_tolerance = replay_tolerance
        self._clock = clock if clock is not None else _utc_now

    def process_donation(self, event: DonationEvent) -> ProcessResult:
        """Apply the rules in order and store the event if new.

        Order is deliberate: replay window before allowlist before duplicate.
        A replayed known event is the real attack shape, so a stale timestamp
        wins even over a disallowed currency or an already-stored id. The
        window is symmetric and inclusive: |now - timestamp| <= tolerance.

        Insertion uses the atomic ``store.add_if_new`` (not exists()+add(),
        which races under parallel delivery); first write wins.
        """
        if abs(self._clock() - event.timestamp) > self._replay_tolerance:
            return ProcessResult.STALE_TIMESTAMP
        if event.currency not in self._allowed_currencies:
            return ProcessResult.CURRENCY_NOT_ALLOWED
        if not self._store.add_if_new(event):
            return ProcessResult.DUPLICATE
        return ProcessResult.CREATED

    def get_donation(self, event_id: str) -> DonationEvent | None:
        """Return a single donation by id, or ``None``."""
        return self._store.get(event_id)

    def list_donations(self) -> list[DonationEvent]:
        """Return all processed donations."""
        return self._store.list_all()

    def compute_stats(self) -> StatsResponse:
        """Aggregate stored donations into per-currency totals and counts."""
        totals: dict[str, Decimal] = {}
        counts: dict[str, int] = {}
        events = self._store.list_all()
        for event in events:
            totals[event.currency] = (
                totals.get(event.currency, Decimal("0")) + event.amount
            )
            counts[event.currency] = counts.get(event.currency, 0) + 1
        by_currency = {
            currency: CurrencyTotal(total=total, count=counts[currency])
            for currency, total in totals.items()
        }
        return StatsResponse(by_currency=by_currency, total_count=len(events))
