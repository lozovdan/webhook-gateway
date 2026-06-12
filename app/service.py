"""Business logic for donation processing.

This layer sits between the HTTP routes and the store. It owns the rules that
are *not* HTTP concerns: the replay window (an event whose timestamp is too
far from "now" in either direction is rejected), the currency allowlist,
idempotency (a repeated ``event_id`` is not stored twice) and statistics
aggregation. The service knows nothing about HTTP status codes.

Time is read through an injected ``clock`` callable, so time-dependent rules
are deterministic in tests.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.models import CurrencyTotal, DonationEvent, StatsResponse
from app.store import DonationStore


def _utc_now() -> datetime:
    """Default clock: the current time as an aware UTC datetime."""
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
        """Create the service.

        Args:
            store: Storage backend to read from and write to.
            allowed_currencies: Injected allowlist (service never reads
                config directly — keeps it unit-testable).
            replay_tolerance: Maximum |now - event.timestamp| accepted;
                events outside this symmetric window are rejected as
                replays. Required — the default lives in config, not here.
            clock: Source of "now" (must return an aware datetime).
                Injectable so time-based tests are deterministic;
                ``None`` means real UTC time.
        """
        self._store = store
        self._allowed_currencies = allowed_currencies
        self._replay_tolerance = replay_tolerance
        self._clock = clock if clock is not None else _utc_now

    def process_donation(self, event: DonationEvent) -> ProcessResult:
        """Apply business rules to a validated event and store it if new.

        Check order: replay window BEFORE allowlist BEFORE duplicate — a
        stale event reports STALE_TIMESTAMP even when its currency is
        disallowed or its event_id is already stored (a replayed known
        event is the actual attack shape). The window is symmetric with an
        inclusive boundary: |now - timestamp| <= tolerance is accepted.

        The insert is delegated to the ATOMIC store.add_if_new(), not
        exists()+add(), which is check-then-act and loses events under
        parallel delivery. First write wins; DUPLICATE never touches
        the stored event.
        """
        if abs(self._clock() - event.timestamp) > self._replay_tolerance:
            return ProcessResult.STALE_TIMESTAMP
        if event.currency not in self._allowed_currencies:
            return ProcessResult.CURRENCY_NOT_ALLOWED
        if not self._store.add_if_new(event):
            return ProcessResult.DUPLICATE
        return ProcessResult.CREATED

    def get_donation(self, event_id: str) -> DonationEvent | None:
        """Return a single donation by id, or ``None`` if not found."""
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
