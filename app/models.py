"""Pydantic models for webhook payloads and API responses.

These schemas are the validation boundary of the service: anything that does
not satisfy the declared types and validators is rejected with HTTP 400
before it ever reaches the business logic.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# Strictly positive money value with at most 2 decimal places.
Money = Annotated[Decimal, Field(gt=0, decimal_places=2)]

# ISO 4217 format: exactly 3 uppercase A-Z letters (no normalisation).
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class DonationEvent(BaseModel):
    """Incoming donation webhook payload.

    Contract:
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
    amount: Money
    currency: CurrencyCode
    timestamp: datetime

    @field_validator("event_id", "donor")
    @classmethod
    def _strip_and_require_non_empty(cls, value: str) -> str:
        """Normalise to the stripped value; reject empty/whitespace-only."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace-only")
        return stripped

    @field_validator("amount", mode="before")
    @classmethod
    def _reject_float_amount(cls, value: object) -> object:
        """Enforce the string contract: float is rejected by type, since
        binary floats cannot represent money exactly (str and int are fine)."""
        if isinstance(value, float):
            raise ValueError('amount must be sent as a string like "10.00", not a float')
        return value


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
