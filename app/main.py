"""FastAPI application factory and HTTP routes.

Routes are intentionally thin: they parse/authenticate the request and
delegate all decisions to :class:`app.service.DonationService`. The mapping
from domain outcomes to HTTP status codes lives here.

Status codes for ``POST /webhooks/donation``:
    200 — accepted and stored
    400 — invalid payload or disallowed currency
    401 — missing/invalid HMAC signature (checked BEFORE payload parsing)
    409 — duplicate ``event_id`` (idempotency)
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models import DonationEvent, StatsResponse
from app.service import DonationService, ProcessResult
from app.signature import verify_signature
from app.store import InMemoryDonationStore

SIGNATURE_HEADER = "X-Signature"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application: fresh store/service per instance.

    Args:
        settings: Runtime config; ``None`` falls back to env via get_settings().
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(title="Webhook Gateway")
    store = InMemoryDonationStore()
    service = DonationService(
        store=store, allowed_currencies=set(settings.allowed_currencies)
    )
    secret = settings.webhook_secret

    async def verified_donation(request: Request) -> DonationEvent:
        """Auth + parse dependency.

        Order: HMAC over the RAW body (missing/bad header -> 401) BEFORE
        manual model_validate_json (ValidationError -> 400, not FastAPI's
        default 422 — we control the code). Broken/empty JSON also raises
        ValidationError, so it lands on 400 too.
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
        """Map ProcessResult to HTTP: CREATED->200, DUPLICATE->409,
        CURRENCY_NOT_ALLOWED->400."""
        result = service.process_donation(event)
        if result is ProcessResult.DUPLICATE:
            raise HTTPException(status_code=409, detail="duplicate event_id")
        if result is ProcessResult.CURRENCY_NOT_ALLOWED:
            raise HTTPException(status_code=400, detail="currency not allowed")
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


# Module-level ASGI app for ``uvicorn app.main:app``.
# TODO: enable once get_settings() (config layer) is implemented:
# app = create_app()
