# Webhook Gateway for donation or payment

[![CI](https://github.com/lozovdan/webhook-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/lozovdan/webhook-gateway/actions/workflows/ci.yml)

A small **FastAPI** service that receives and processes donation/payment
webhook events from external platforms. It is a **portfolio project** inspired by
my production work on a donation platform (closed-source), built from scratch in Python
to demonstrate engineering practices and **deep automated testing + CI**, not
feature breadth.

## Features

- `POST /webhooks/donation` — ingest a donation event
  - HMAC-SHA256 signature check over the raw request body (`X-Signature` header, shared secret)
  - Pydantic v2 payload validation (amount > 0, max 2 decimal places, string-typed money, currency format, timezone-aware timestamp, required fields)
  - Replay protection: events with a timestamp outside a symmetric tolerance window are rejected; the clock is injected for deterministic time-based tests
  - Currency allowlist enforced in the service layer
  - Idempotency: a repeated `event_id` is not processed twice (first write wins), race-free under parallel delivery, the insert is atomic in the store (`add_if_new`, the in-memory analogue of a unique-constraint INSERT)
  - Status codes: `200` ok · `400` bad payload / disallowed currency / stale timestamp · `401` bad signature · `409` duplicate
- `GET /donations` — list processed events (insertion order)
- `GET /donations/{event_id}` — fetch one event (`404` if missing)
- `GET /health` — health check
- `GET /stats` — per-currency aggregates (exact `Decimal` totals, serialized as JSON strings)

## Tech stack

- Python 3.12+, FastAPI, Pydantic v2
- pytest, httpx (TestClient), pytest-cov, hypothesis, mutmut
- ruff + mypy (strict) enforced in CI
- In-memory storage (dict) behind a swappable `DonationStore` interface
- Docker (multi-stage, non-root) + Compose for a one-command run
- GitHub Actions for CI: lint -> types -> tests with coverage gate

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

The whole service was built TDD. 127 tests, 100% line + branch coverage
(abstract-method bodies excluded as unreachable by definition), CI gate at 90%.

`tests/test_properties.py` adds property-based tests (hypothesis): instead of
hand-picked examples they state invariants, so any signed body verifies, any
tampered body or garbage header fails closed without raising, any positive
2-dp decimal string is accepted exactly and survives a JSON round-trip, any
float is rejected, and hypothesis hunts for counterexamples.

Line coverage says which code the tests run; mutation testing (mutmut) says
which behaviour they pin. Score: **156/157 mutants killed**. The
first run left 18 survivors: those were part of the contract, so the tests now
pin them. The one survivor is an equivalent mutant: `encode("utf-8")` → `encode("UTF-8")`,
codec lookup is case-insensitive.

```bash
mutmut run        # mutate app/, run the suite against each mutant
mutmut results    # list survivors
```

Highlight: `tests/test_concurrency.py` reproduces the idempotency TOCTOU race
**deterministically**. A barrier-instrumented store forces every racing thread
to pass the existence check before any write, so the worst-case interleaving
happens on every run. The red phase of that test caught a real bug: `exists()` + `add()`
in the service let N parallel deliveries of one event all report `created`
instead of one `created` and N−1 duplicates.

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

## Run with Docker

The image is multi-stage (build tooling stays out of the final layer), runs as
a **non-root** user and ships **runtime dependencies only**.

```bash
# 1. Provide configuration
cp .env.example .env          # then set WEBHOOK_SECRET

# 2. Build and start
docker compose up --build     # serves on http://localhost:8000

curl localhost:8000/health    # {"status":"ok"}
```

Without compose:

```bash
docker build -t webhook-gateway .
docker run -p 8000:8000 -e WEBHOOK_SECRET="change-me" webhook-gateway
```

A `HEALTHCHECK` probes `/health`, so `docker ps` reports the container as
`healthy` once it is ready to serve.

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
