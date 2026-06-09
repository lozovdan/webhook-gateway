"""FastAPI application factory and HTTP routes.

Routes are intentionally thin: they parse/authenticate the request and
delegate all decisions to :class:`app.service.DonationService`. The mapping
from domain outcomes to HTTP status codes lives here.

Status codes for ``POST /webhooks/donation``:
    200 — accepted and stored
    400 — invalid payload (Pydantic validation error)
    401 — missing/invalid HMAC signature
    409 — duplicate ``event_id`` (idempotency)
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Wires together settings, the store and the service, and registers all
    routes described in ``CLAUDE.md``:

        POST /webhooks/donation   — ingest a donation event
        GET  /donations           — list processed events
        GET  /donations/{id}      — fetch one event (404 if missing)
        GET  /health              — liveness check
        GET  /stats               — aggregated totals by currency

    Returns:
        A ready-to-serve :class:`fastapi.FastAPI` instance.
    """
    raise NotImplementedError


# Module-level ASGI app for ``uvicorn app.main:app``.
# TODO: enable once create_app() is implemented.
# app = create_app()
