"""Property-based tests (hypothesis): invariants that hold for ALL inputs.

The example-based suites pin specific, human-chosen cases. These tests state
invariants over arbitrary inputs and let hypothesis search for a
counterexample, then shrink it to a minimal repro.

Scope is the two pure-logic hotspots:
    - HMAC signatures (app/signature.py): round-trip always verifies;
      a different body, a different secret or arbitrary garbage in the
      header never verifies and never raises (fail closed).
    - The money contract (app/models.py): every positive 2-dp decimal sent
      as a string is accepted EXACTLY; every float is rejected; a model
      survives a JSON round-trip identically (Decimal serialized as a JSON
      string, never a float).

Note on assume(x != y): HMAC-SHA256 collisions between different inputs are
possible in principle; the tests treat them as impossible in practice, which
is exactly the property the signature scheme relies on.
"""

from decimal import Decimal

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models import DonationEvent
from app.signature import generate_signature, verify_signature
from tests.conftest import make_payload

# Bodies are arbitrary bytes and secrets arbitrary non-empty text: the
# signature layer must not care what is inside either.
bodies = st.binary()
secrets = st.text(min_size=1)

# Strictly positive money with exactly <= 2 decimal places, as the model
# accepts it. The upper bound only keeps shrunk repros readable.
money = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# signature properties


@given(body=bodies, secret=secrets)
def test_generated_signature_always_verifies(body: bytes, secret: str) -> None:
    """Round-trip: verify(body, s, generate(body, s)) holds for ANY body and
    secret, including the empty body and non-ASCII secrets."""
    assert verify_signature(body, secret, generate_signature(body, secret)) is True


@given(body=bodies, other=bodies, secret=secrets)
def test_signature_of_other_body_never_verifies(
    body: bytes, other: bytes, secret: str
) -> None:
    """A signature taken from ANY different body is rejected (tampering)."""
    assume(body != other)

    assert verify_signature(body, secret, generate_signature(other, secret)) is False


@given(body=bodies, secret=secrets, other_secret=secrets)
def test_signature_under_other_secret_never_verifies(
    body: bytes, secret: str, other_secret: str
) -> None:
    """A signature made with ANY different secret is rejected."""
    assume(secret != other_secret)

    signature = generate_signature(body, other_secret)

    assert verify_signature(body, secret, signature) is False


@given(body=bodies, secret=secrets, junk=st.text())
def test_arbitrary_header_text_fails_closed(
    body: bytes, secret: str, junk: str
) -> None:
    """ANY text in the signature header that is not the real signature gives
    False, never an exception. Includes non-ASCII text, where
    hmac.compare_digest itself would raise TypeError: the verifier must
    swallow that and fail closed."""
    assume(junk != generate_signature(body, secret))

    assert verify_signature(body, secret, junk) is False


# money contract properties


@given(amount=money)
def test_any_valid_money_string_is_accepted_exactly(amount: Decimal) -> None:
    """Every positive 2-dp decimal sent as a string is accepted with the
    EXACT value."""
    event = DonationEvent(**make_payload(amount=str(amount)))

    assert event.amount == amount


@given(amount=st.floats(min_value=0.01, allow_nan=False, allow_infinity=False))
def test_any_float_amount_is_rejected(amount: float) -> None:
    """No float is ever accepted."""
    with pytest.raises(ValidationError):
        DonationEvent(**make_payload(amount=amount))


@given(amount=money)
def test_event_survives_json_roundtrip_exactly(amount: Decimal) -> None:
    """model_dump_json -> model_validate_json is the identity: the Decimal
    comes back exactly, which also proves it is serialized as a JSON string."""
    event = DonationEvent(**make_payload(amount=str(amount)))

    restored = DonationEvent.model_validate_json(event.model_dump_json())

    assert restored == event


@given(donor=st.text(min_size=1).filter(lambda s: s.strip()))
def test_donor_is_normalised_to_stripped_value(donor: str) -> None:
    """For ANY donor with visible content, the model stores exactly
    donor.strip(), normalisation is total, not just for ASCII spaces."""
    event = DonationEvent(**make_payload(donor=donor))

    assert event.donor == donor.strip()
