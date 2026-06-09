"""Webhook Gateway application package.

A small FastAPI service that ingests donation webhook events, validates and
authenticates them (HMAC), stores them idempotently, and exposes a few
read/aggregation endpoints. See ``CLAUDE.md`` for the full specification.
"""

__version__ = "0.1.0"
