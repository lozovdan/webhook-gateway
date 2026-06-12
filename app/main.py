"""FastAPI application factory and HTTP routes.

Routes are thin: they authenticate, parse, and map domain outcomes to HTTP
status codes, delegating all decisions to :class:`app.service.DonationService`.

POST /webhooks/donation: 200 stored; 400 bad payload/currency/stale
timestamp; 401 bad signature; 409 duplicate.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models import DonationEvent, StatsResponse
from app.service import DonationService, ProcessResult
from app.signature import verify_signature
from app.store import InMemoryDonationStore

SIGNATURE_HEADER = "X-Signature"


def create_app(
    settings: Settings | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Build the app with a fresh store/service per instance.

    ``settings`` falls back to env; ``clock`` is injectable so API tests
    control time deterministically (None means real UTC time).
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(title="Webhook Gateway")
    store = InMemoryDonationStore()
    service = DonationService(
        store=store,
        allowed_currencies=set(settings.allowed_currencies),
        replay_tolerance=timedelta(seconds=settings.replay_tolerance_seconds),
        clock=clock,
    )
    secret = settings.webhook_secret

    async def verified_donation(request: Request) -> DonationEvent:
        """Auth then parse. HMAC over the RAW body first (missing/bad -> 401),
        then manual model_validate_json so validation errors map to 400, not
        FastAPI's default 422. Broken/empty JSON also lands on 400.
        """
        raw = await request.body()
        signature = request.headers.get(SIGNATURE_HEADER)
        if signature is None or not verify_signature(raw, secret, signature):
            raise HTTPException(status_code=401, detail="missing or invalid signature")
        try:
            return DonationEvent.model_validate_json(raw)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail="invalid payload") from exc

    @app.post("/webhooks/donation")
    async def receive_donation(
        event: DonationEvent = Depends(verified_donation),
    ) -> dict[str, str]:
        result = service.process_donation(event)
        if result is ProcessResult.DUPLICATE:
            raise HTTPException(status_code=409, detail="duplicate event_id")
        if result is ProcessResult.CURRENCY_NOT_ALLOWED:
            raise HTTPException(status_code=400, detail="currency not allowed")
        if result is ProcessResult.STALE_TIMESTAMP:
            raise HTTPException(
                status_code=400, detail="timestamp outside replay tolerance window"
            )
        return {"status": "created", "event_id": event.event_id}

    @app.get("/donations")
    def list_donations() -> list[DonationEvent]:
        return service.list_donations()

    @app.get("/donations/{event_id}")
    def get_donation(event_id: str) -> DonationEvent:
        event = service.get_donation(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="donation not found")
        return event

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/stats")
    def stats() -> StatsResponse:
        return service.compute_stats()

    return app


def __getattr__(name: str) -> FastAPI:
    """Lazy module-level ``app`` for ``uvicorn app.main:app``, so
    importing this module never requires WEBHOOK_SECRET to be set.
    """
    if name == "app":
        return create_app()
    raise AttributeError(name)
