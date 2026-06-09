"""Pydantic models for webhook payloads and API responses.

These schemas are the validation boundary of the service: anything that does
not satisfy the declared types and validators is rejected with HTTP 400
before it ever reaches the business logic.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DonationEvent(BaseModel):
    """Incoming donation webhook payload.

    Contract (field constraints are added in the green phase):
        event_id:  str, non-empty after stripping whitespace (used for
                   idempotency).
        donor:     str, non-empty after stripping whitespace.
        amount:    Decimal, strictly > 0, at most 2 decimal places. MUST be
                   supplied as a JSON string ("10.00"); float input is
                   rejected by TYPE (strict), not merely when binary-float
                   imprecision expands it past 2 decimal places.
        currency:  ISO 4217 code — exactly 3 uppercase letters (format only;
                   allowlist membership is enforced in the service layer).
        timestamp: datetime.
    """

    event_id: str
    donor: str
    amount: Decimal
    currency: str
    timestamp: datetime


class CurrencyTotal(BaseModel):
    """Aggregated total for a single currency.

    Minimal stub — fields (currency, total, count) are designed together with
    the /stats aggregation in the service-layer step.
    """

    # TODO: define fields when building the service/stats layer


class StatsResponse(BaseModel):
    """Aggregated statistics across processed donations.

    Minimal stub — fields (count, by_currency) are designed together with the
    /stats aggregation in the service-layer step.
    """

    # TODO: define fields when building the service/stats layer
