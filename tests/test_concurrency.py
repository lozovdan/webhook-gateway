"""Concurrency: idempotency must hold under parallel delivery.

Webhook providers retry and deliver in parallel, so two copies of one event
can arrive at once. ``BarrierStore`` reproduces the worst-case interleaving
deterministically: every racing thread finishes its existence check before
any write, so the old check-then-act (exists() + add()) lets them all observe
"absent" and write. The fix is the store's atomic ``add_if_new``; the service
maps its outcome to DUPLICATE.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress

from app.service import DonationService, ProcessResult
from app.store import InMemoryDonationStore
from tests.test_service import ALLOWED_CURRENCIES, FIXED_NOW, TOLERANCE, make_event

THREADS = 8


class BarrierStore(InMemoryDonationStore):
    """Forces the worst-case interleaving: ``exists()`` blocks until all
    racing threads have finished their check, so every caller sees the event
    as absent before any write. The timeout + suppressed BrokenBarrierError
    keep the suite from hanging once the implementation is atomic and no
    longer calls exists().
    """

    def __init__(self, parties: int) -> None:
        super().__init__()
        self._barrier = threading.Barrier(parties)

    def exists(self, event_id: str) -> bool:  # noqa: D102
        result = super().exists(event_id)
        with suppress(threading.BrokenBarrierError):
            self._barrier.wait(timeout=2.0)
        return result


def _make_service(store: InMemoryDonationStore) -> DonationService:
    """Service on the given store with the frozen test clock."""
    return DonationService(
        store=store,
        allowed_currencies=ALLOWED_CURRENCIES,
        replay_tolerance=TOLERANCE,
        clock=lambda: FIXED_NOW,
    )


def test_parallel_same_event_id_yields_exactly_one_created() -> None:
    """N threads deliver the SAME event simultaneously under the forced
    worst-case interleaving: exactly one CREATED, the rest DUPLICATE, and
    exactly one stored copy."""
    store = BarrierStore(parties=THREADS)
    service = _make_service(store)
    event = make_event("evt_race")

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = list(
            pool.map(lambda _: service.process_donation(event), range(THREADS))
        )

    assert results.count(ProcessResult.CREATED) == 1
    assert results.count(ProcessResult.DUPLICATE) == THREADS - 1
    assert len(store.list_all()) == 1


def test_store_add_if_new_unsynchronised_contention() -> None:
    """Plain store, no forced interleaving: many threads race add_if_new for
    one event_id; exactly one wins. Complements the deterministic test above
    by exercising the real, uninstrumented implementation."""
    store = InMemoryDonationStore()
    event = make_event("evt_race")

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        outcomes = list(pool.map(lambda _: store.add_if_new(event), range(THREADS)))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == THREADS - 1
    assert len(store.list_all()) == 1
