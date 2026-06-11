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

from fastapi import Depends, FastAPI, Request

from app.config import Settings, get_settings
from app.models import DonationEvent, StatsResponse
from app.service import DonationService
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
    del service  # wired into the route bodies in the green phase

    async def verified_donation(request: Request) -> DonationEvent:
        """Auth + parse dependency.

        Order: HMAC over the RAW body (missing/bad header -> 401) BEFORE
        manual model_validate_json (validation error -> 400, not FastAPI's
        default 422 — we control the code).
        """
        raise NotImplementedError

    @app.post("/webhooks/donation")
    async def receive_donation(
        event: DonationEvent = Depends(verified_donation),
    ) -> dict[str, str]:
        """Maps ProcessResult: CREATED->200, DUPLICATE->409,
        CURRENCY_NOT_ALLOWED->400."""
        raise NotImplementedError

    @app.get("/donations")
    def list_donations() -> list[DonationEvent]:
        raise NotImplementedError

    @app.get("/donations/{event_id}")
    def get_donation(event_id: str) -> DonationEvent:
        raise NotImplementedError

    @app.get("/health")
    def health() -> dict[str, str]:
        raise NotImplementedError

    @app.get("/stats")
    def stats() -> StatsResponse:
        raise NotImplementedError

    return app


# Module-level ASGI app for ``uvicorn app.main:app``.
# TODO: enable once the routes are implemented.
# app = create_app()
