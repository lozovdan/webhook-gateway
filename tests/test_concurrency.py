"""Concurrency tests: idempotency must hold under parallel delivery.

Webhook providers retry aggressively and deliver in parallel, so two copies
of the same event can arrive at the same time. Idempotency that only holds
for sequential calls is not idempotency.

Red phase: process_donation does check-then-act (store.exists(), then
store.add()) — a TOCTOU race. The async route currently masks it (a single
event loop thread never interleaves the two calls), but the service must not
depend on its caller's threading model: a sync route in FastAPI's threadpool
or a second worker thread would expose it.

The race is reproduced DETERMINISTICALLY:
``BarrierStore.exists()`` blocks until every racing thread has finished its
check, so all of them observe "absent" before any write happens, the
worst-case interleaving on every single run.

Decision locked here: the atomic "insert if new" belongs to the STORE
(``add_if_new``, the analogue of a DB unique-constraint INSERT); the service
maps its outcome to DUPLICATE. exists()+add() in the service can never be
made race-free from the outside.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress

from app.service import DonationService, ProcessResult
from app.store import InMemoryDonationStore
from tests.test_service import ALLOWED_CURRENCIES, FIXED_NOW, TOLERANCE, make_event

THREADS = 8


class BarrierStore(InMemoryDonationStore):
    """Store that forces the worst-case interleaving for check-then-act.

    ``exists()`` waits until ALL racing threads have finished their check
    before returning, so every caller sees the event as absent before any
    of them gets to write. The timeout keeps the suite from hanging when
    fewer than ``parties`` callers ever reach exists() (e.g. once the
    implementation is atomic and no longer calls it); the resulting
    BrokenBarrierError is suppressed because in that case there is no
    interleaving left to force.
    """

    def __init__(self, parties: int) -> None:
        super().__init__()
        self._barrier = threading.Barrier(parties)

    def exists(self, event_id: str) -> bool:  # noqa: D102 (see class docstring)
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
