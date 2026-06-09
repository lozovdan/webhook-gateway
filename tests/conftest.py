"""Shared pytest fixtures.

Planned fixtures (to be implemented):
    settings        — test Settings with a known secret + currency allowlist.
    store           — a fresh InMemoryDonationStore for every test (isolation).
    app             — FastAPI app wired to the test store/settings.
    client          — httpx/Starlette TestClient bound to ``app``.
    valid_payload   — a factory returning a well-formed donation dict.
    sign            — helper that returns a valid X-Signature for given bytes.
    auth_headers    — helper building headers (incl. valid signature) for a body.

Goal: each test starts from a clean, deterministic state so cases never leak
into one another.
"""

from __future__ import annotations

# TODO: import pytest, TestClient, app factory, store, signature helper
# TODO: implement the fixtures listed above
