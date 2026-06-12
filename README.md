# Webhook Gateway for donation or payment

[![CI](https://github.com/lozovdan/webhook-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/lozovdan/webhook-gateway/actions/workflows/ci.yml)

A small **FastAPI** service that receives and processes donation/payment
webhook events from external platforms. It is a **portfolio project** inspired by
my production work on a donation platform (closed-source), built from scratch in Python
to demonstrate engineering practices and **deep automated testing + CI**, not
feature breadth.

## Features

- `POST /webhooks/donation` — ingest a donation event
  - HMAC-SHA256 signature check over the **raw request body** (`X-Signature` header, shared secret)
  - Pydantic v2 payload validation (amount > 0, max 2 decimal places, string-typed money, currency format, timezone-aware timestamp, required fields)
  - Replay protection: events with a timestamp outside a symmetric tolerance window (default ±300 s, like Stripe) are rejected; the clock is injected for deterministic time-based tests
  - Currency allowlist enforced in the service layer
  - Idempotency: a repeated `event_id` is not processed twice (first write wins)
  - Status codes: `200` ok · `400` bad payload / disallowed currency / stale timestamp · `401` bad signature · `409` duplicate
- `GET /donations` — list processed events (insertion order)
- `GET /donations/{event_id}` — fetch one event (`404` if missing)
- `GET /health` — health check
- `GET /stats` — per-currency aggregates (exact `Decimal` totals, serialized as JSON strings)

## Tech stack

- Python 3.12+, FastAPI, Pydantic v2
- pytest, httpx (TestClient), pytest-cov
- In-memory storage (dict) behind a swappable `DonationStore` interface
- GitHub Actions for CI

## Architecture

The code is split into thin layers so each can be tested in isolation:

| Module             | Responsibility                                       |
| ------------------ | ---------------------------------------------------- |
| `app/main.py`      | FastAPI app factory + routes (HTTP mapping only)     |
| `app/models.py`    | Pydantic schemas (validation boundary)               |
| `app/signature.py` | HMAC signature generation/verification (timing-safe) |
| `app/store.py`     | Storage interface + in-memory implementation         |
| `app/service.py`   | Business logic (allowlist, idempotency, aggregation) |
| `app/config.py`    | Settings (secret, currency allowlist) from env       |

## Testing

The whole service was built TDD. 115 tests, ~98% coverage, CI gate at 90%.

## Getting started

```bash
# Create a virtualenv, then install runtime + dev dependencies
python -m pip install -e ".[dev]"

# Configure required settings (no secrets are hard-coded)
export WEBHOOK_SECRET="change-me"
export ALLOWED_CURRENCIES="USD,EUR,CZK"   # optional

# Run the service
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest                       # uses settings from pyproject.toml (incl. --cov)
pytest --cov-report=html     # HTML coverage report in htmlcov/
```

Tests need no environment variables — settings are injected explicitly.
Coverage gate: **90%** (`fail_under = 90`, enforced locally and in CI).

## Configuration

| Variable                   | Required | Default       | Description                                                                    |
| -------------------------- | -------- | ------------- | ------------------------------------------------------------------------------ |
| `WEBHOOK_SECRET`           | yes      | —             | Shared secret for the `X-Signature` HMAC; empty value refuses to start         |
| `ALLOWED_CURRENCIES`       | no       | `USD,EUR,CZK` | Comma-separated allowlist (strip+upper); set-but-empty is an error             |
| `REPLAY_TOLERANCE_SECONDS` | no       | `300`         | Symmetric replay window in seconds; must be a positive integer (no off switch) |

## License

MIT — see [LICENSE](LICENSE).
