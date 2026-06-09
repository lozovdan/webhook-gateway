"""HMAC signature generation and verification.

Webhook authenticity is proven with an HMAC-SHA256 over the *raw* request
body using a shared secret. The signature is transported in the
``X-Signature`` header. Verification must be constant-time to avoid timing
side channels.
"""

from __future__ import annotations


def generate_signature(body: bytes, secret: str) -> str:
    """Compute the hex-encoded HMAC-SHA256 of ``body``.

    Args:
        body: The raw request body bytes that were/are signed.
        secret: The shared secret key.

    Returns:
        Lowercase hex digest of the HMAC-SHA256.
    """
    raise NotImplementedError


def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Check a provided signature against the expected one.

    Compares using :func:`hmac.compare_digest` so that timing does not leak
    how much of the signature matched. Any invalid or garbage input in
    ``signature`` (non-hex, empty string, wrong length) must result in a
    ``False`` return value rather than a raised exception.

    Args:
        body: The raw request body bytes.
        secret: The shared secret key.
        signature: The signature received in the ``X-Signature`` header.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    raise NotImplementedError
