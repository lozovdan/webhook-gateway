"""Pydantic models for webhook payloads and API responses.

These schemas are the validation boundary: anything that fails the declared
types/validators is rejected (HTTP 400) before it reaches business logic.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field, field_validator

# Strictly positive money, at most 2 decimal places.
Money = Annotated[Decimal, Field(gt=0, decimal_places=2)]

# ISO 4217 format only: exactly 3 uppercase letters. Allowlist membership is
# enforced in the service layer, not here.
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class DonationEvent(BaseModel):
    """Incoming donation webhook payload.

    Two non-obvious rules:
    - ``amount`` must arrive as a JSON string ("10.00"); float is rejected by
      type, since binary floats can't represent money exactly.
    - ``timestamp`` must be timezone-aware. A naive value is rejected, not
      assumed UTC: comparing naive/aware datetimes raises, and guessing the
      sender's zone would silently shift the replay window.
    """

    event_id: str
    donor: str
    amount: Money
    currency: CurrencyCode
    timestamp: AwareDatetime

    @field_validator("event_id", "donor")
    @classmethod
    def _strip_and_require_non_empty(cls, value: str) -> str:
        """Strip, and reject empty/whitespace-only."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace-only")
        return stripped

    @field_validator("amount", mode="before")
    @classmethod
    def _reject_float_amount(cls, value: object) -> object:
        """Reject float (str and int are accepted)."""
        if isinstance(value, float):
            raise ValueError(
                'amount must be sent as a string like "10.00", not a float'
            )
        return value


class CurrencyTotal(BaseModel):
    """Per-currency aggregate: exact Decimal total and event count."""

    total: Decimal
    count: int


class StatsResponse(BaseModel):
    """Stats grouped by currency, currencies are never summed together."""

    by_currency: dict[str, CurrencyTotal]
    total_count: int
