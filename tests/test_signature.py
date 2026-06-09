"""Unit tests for app.signature (HMAC generation/verification).

Red phase (TDD): these tests describe the contract of generate_signature /
verify_signature before the implementation exists. They are expected to fail
with NotImplementedError until the signature layer is implemented.
"""

from collections.abc import Callable

import pytest

from app.signature import generate_signature, verify_signature

# Shared test fixtures-as-constants.
SECRET = "super-secret-shared-key"
OTHER_SECRET = "a-different-secret-key"
BODY = b'{"event_id": "evt_1", "amount": "10.00", "currency": "USD"}'
OTHER_BODY = b'{"event_id": "evt_1", "amount": "99.99", "currency": "USD"}'

# A builder returns the (body, secret, signature) triple to feed verify_signature.
InvalidCaseBuilder = Callable[[], tuple[bytes, str, str]]


def test_generate_signature_same_input_returns_same_digest() -> None:
    """Generation is deterministic: identical body+secret -> identical digest."""
    first: str = generate_signature(BODY, SECRET)
    second: str = generate_signature(BODY, SECRET)

    assert first == second


def test_generate_signature_different_body_returns_different_digest() -> None:
    """Different bodies under the same secret produce different digests."""
    assert generate_signature(BODY, SECRET) != generate_signature(OTHER_BODY, SECRET)


def test_verify_signature_valid_roundtrip_returns_true() -> None:
    """A freshly generated signature verifies against its own body+secret."""
    signature: str = generate_signature(BODY, SECRET)

    assert verify_signature(BODY, SECRET, signature) is True


def _tampered_body_case() -> tuple[bytes, str, str]:
    """Valid signature for BODY, but checked against a different body."""
    signature: str = generate_signature(BODY, SECRET)
    return OTHER_BODY, SECRET, signature


def _wrong_secret_case() -> tuple[bytes, str, str]:
    """Valid signature for SECRET, but verified with another secret."""
    signature: str = generate_signature(BODY, SECRET)
    return BODY, OTHER_SECRET, signature


def _non_hex_signature_case() -> tuple[bytes, str, str]:
    """Garbage, non-hex signature string must be rejected, not raise."""
    return BODY, SECRET, "definitely-not-hex-zzz!!"


def _empty_signature_case() -> tuple[bytes, str, str]:
    """Empty signature string must be rejected, not raise."""
    return BODY, SECRET, ""


def _non_ascii_signature_case() -> tuple[bytes, str, str]:
    """Non-ASCII signature: hmac.compare_digest raises TypeError internally,
    which verify_signature must swallow and turn into False (not propagate)."""
    return BODY, SECRET, "кириллица"


@pytest.mark.parametrize(
    "build_case",
    [
        pytest.param(_tampered_body_case, id="tampered-body"),
        pytest.param(_wrong_secret_case, id="wrong-secret"),
        pytest.param(_non_hex_signature_case, id="non-hex-signature"),
        pytest.param(_empty_signature_case, id="empty-signature"),
        pytest.param(_non_ascii_signature_case, id="non-ascii-signature"),
    ],
)
def test_verify_signature_invalid_input_returns_false(
    build_case: InvalidCaseBuilder,
) -> None:
    """Tampering, wrong secret, or malformed signatures all return False."""
    body, secret, signature = build_case()

    assert verify_signature(body, secret, signature) is False


def test_generate_and_verify_empty_body_roundtrip_returns_true() -> None:
    """An empty body is signable and the signature round-trips successfully."""
    signature: str = generate_signature(b"", SECRET)

    assert isinstance(signature, str)
    assert verify_signature(b"", SECRET, signature) is True
