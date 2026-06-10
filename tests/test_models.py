"""Unit tests for app.models (Pydantic validation of DonationEvent).

Red phase (TDD): these tests describe the validation contract before the
constraints/validators exist on the model. The negative cases are expected to
fail now (the stub accepts anything) and to pass once the green phase adds
gt=0, decimal_places=2, the currency pattern, the float-rejecting strict
type check and strip-based non-empty checks.

Design decisions locked in by these tests:
    - currency is validated for FORMAT only (exactly 3 uppercase A-Z letters);
      lowercase is REJECTED, not auto-normalised. Allowlist membership is a
      service-layer concern, not a model concern.
    - amount MUST arrive as a JSON string ("10.00"). ANY float input is
      rejected by TYPE.
    - event_id and donor must be non-empty AFTER stripping: a whitespace-only
      string is as invalid as an empty one.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import DonationEvent

# A single well-formed payload; individual tests override or drop fields.
VALID_PAYLOAD: dict[str, object] = {
    "event_id": "evt_001",
    "donor": "Alice Donor",
    "amount": "10.00",
    "currency": "USD",
    "timestamp": "2026-06-09T12:00:00Z",
}


def _payload(**overrides: object) -> dict[str, object]:
    """Return a copy of the valid payload with the given field overrides."""
    return {**VALID_PAYLOAD, **overrides}


def _payload_without(field: str) -> dict[str, object]:
    """Return a copy of the valid payload with ``field`` removed."""
    data = dict(VALID_PAYLOAD)
    data.pop(field)
    return data


def _error_fields(exc: ValidationError) -> set[str]:
    """Collect the names of the fields that failed validation."""
    return {str(err["loc"][-1]) for err in exc.errors() if err["loc"]}


def _error_types_for(exc: ValidationError, field: str) -> set[str]:
    """Collect the Pydantic error 'type' codes raised for a specific field."""
    return {
        err["type"] for err in exc.errors() if err["loc"] and err["loc"][-1] == field
    }


def test_donationevent_valid_payload_creates_typed_object() -> None:
    """A well-formed payload builds an object with correctly typed fields."""
    event = DonationEvent(**_payload())

    assert event.event_id == "evt_001"
    assert event.donor == "Alice Donor"
    assert isinstance(event.amount, Decimal)
    assert event.amount == Decimal("10.00")
    assert event.currency == "USD"
    assert isinstance(event.timestamp, datetime)


def test_donationevent_int_amount_is_accepted() -> None:
    """int is part of the amount contract (str and int — yes, float — no)."""
    event = DonationEvent(**_payload(amount=7))

    assert event.amount == Decimal("7")


@pytest.mark.parametrize(
    ("amount", "expected_type"),
    [
        pytest.param("-5.00", "greater_than", id="negative-amount"),
        pytest.param("0.00", "greater_than", id="zero-amount-gt-not-ge"),
        pytest.param("10.001", "decimal_max_places", id="three-decimal-places"),
    ],
)
def test_donationevent_invalid_amount_raises(amount: str, expected_type: str) -> None:
    """Amounts that are <= 0 or have more than two decimal places are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload(amount=amount))

    assert expected_type in _error_types_for(exc_info.value, "amount")


@pytest.mark.parametrize(
    "currency",
    [
        pytest.param("US", id="two-letters-too-short"),
        pytest.param("USDX", id="four-letters-too-long"),
        pytest.param("usd", id="lowercase-rejected-not-normalised"),
        pytest.param("US1", id="contains-digit"),
        pytest.param("U$D", id="contains-symbol"),
    ],
)
def test_donationevent_invalid_currency_format_raises(currency: str) -> None:
    """currency must be exactly three uppercase A-Z letters (format only)."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload(currency=currency))

    assert "currency" in _error_fields(exc_info.value)


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("event_id", id="missing-event_id"),
        pytest.param("donor", id="missing-donor"),
        pytest.param("amount", id="missing-amount"),
        pytest.param("currency", id="missing-currency"),
        pytest.param("timestamp", id="missing-timestamp"),
    ],
)
def test_donationevent_missing_required_field_raises(field: str) -> None:
    """Every field is required; dropping any one is a validation error."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload_without(field))

    assert "missing" in _error_types_for(exc_info.value, field)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("event_id", "", id="empty-event_id"),
        pytest.param("donor", "", id="empty-donor"),
        pytest.param("event_id", "   ", id="whitespace-only-event_id"),
        pytest.param("donor", "   ", id="whitespace-only-donor"),
    ],
)
def test_donationevent_blank_string_field_raises(field: str, value: str) -> None:
    """event_id and donor must be non-empty after stripping whitespace."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload(**{field: value}))

    assert field in _error_fields(exc_info.value)


@pytest.mark.parametrize(
    "amount",
    [
        pytest.param(10.5, id="plain-float-rejected-by-type"),
        pytest.param(0.1 + 0.2, id="imprecise-float-why-floats-are-banned"),
    ],
)
def test_donationevent_float_amount_is_rejected(amount: float) -> None:
    """ANY float amount is rejected by type — the string contract is enforced."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload(amount=amount))

    assert "amount" in _error_fields(exc_info.value)
