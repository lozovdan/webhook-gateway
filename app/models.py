"""Pydantic models for webhook payloads and API responses.

These schemas are the validation boundary of the service: anything that does
not satisfy the declared types and validators is rejected with HTTP 400
before it ever reaches the business logic.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DonationEvent(BaseModel):
    """Incoming donation webhook payload.

    Planned fields / rules (to be implemented):
        event_id (str):   Unique id of the event; used for idempotency.
        donor (str):      Display name or handle of the donor.
        amount (Decimal): Monetary amount; must be strictly > 0.
        currency (str):   Uppercase code; must be in the configured allowlist.
        timestamp (datetime): When the donation occurred.
    """

    # TODO: declare fields with types + validators
    #   - amount must be > 0 (field/validator)
    #   - currency normalised to uppercase and checked against allowlist
    #   - all fields required (no implicit defaults)


class CurrencyTotal(BaseModel):
    """Aggregated total for a single currency.

    Planned fields:
        currency (str):     ISO currency code.
        total (Decimal):    Sum of donation amounts in that currency.
        count (int):        Number of donations in that currency.
    """

    # TODO: declare fields


class StatsResponse(BaseModel):
    """Aggregated statistics across all processed donations.

    Planned fields:
        count (int):                 Total number of processed donations.
        by_currency (list[CurrencyTotal]): Per-currency totals and counts.
    """

    # TODO: declare fields
