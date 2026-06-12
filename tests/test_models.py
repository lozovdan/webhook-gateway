"""Unit tests for app.models (Pydantic validation of DonationEvent).

Contract decisions exercised:
- currency is format-only (3 uppercase A-Z letters); lowercase is rejected,
  not normalised. Allowlist membership is a service concern.
- amount must arrive as a JSON string; any float is rejected by type.
- event_id and donor must be non-empty after stripping.
- timestamp must be timezone-aware; a naive value is rejected, not assumed
  UTC (comparing naive/aware datetimes raises, and guessing the zone would
  shift the replay window). Any explicit offset is fine.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import DonationEvent

# A single well-formed payload; individual tests override or drop fields.
# dict[str, Any] on purpose: negative tests override fields with junk.
VALID_PAYLOAD: dict[str, Any] = {
    "event_id": "evt_001",
    "donor": "Alice Donor",
    "amount": "10.00",
    "currency": "USD",
    "timestamp": "2026-06-09T12:00:00Z",
}


def _payload(**overrides: object) -> dict[str, Any]:
    """Return a copy of the valid payload with the given field overrides."""
    return {**VALID_PAYLOAD, **overrides}


def _payload_without(field: str) -> dict[str, Any]:
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
    """int is part of the amount contract."""
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
    """ANY float amount is rejected by type."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload(amount=amount))

    assert "amount" in _error_fields(exc_info.value)


@pytest.mark.parametrize(
    "timestamp",
    [
        pytest.param("2026-06-09T12:00:00", id="naive-iso-string"),
        pytest.param(datetime(2026, 6, 9, 12, 0, 0), id="naive-datetime-object"),
    ],
)
def test_donationevent_naive_timestamp_is_rejected(timestamp: object) -> None:
    """A timestamp without timezone info is a contract violation, not 'UTC'."""
    with pytest.raises(ValidationError) as exc_info:
        DonationEvent(**_payload(timestamp=timestamp))

    assert "timestamp" in _error_fields(exc_info.value)


def test_donationevent_timestamp_with_any_utc_offset_is_accepted() -> None:
    """Aware non-UTC timestamps are valid and denote the correct instant."""
    event = DonationEvent(**_payload(timestamp="2026-06-09T14:00:00+02:00"))

    assert event.timestamp.utcoffset() is not None
    assert event.timestamp == datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
