"""HMAC-SHA256 over the raw request body, keyed by a shared secret.

Verification is constant-time to avoid leaking how much of the signature
matched (a timing side channel).
"""

from __future__ import annotations

import hashlib
import hmac


def generate_signature(body: bytes, secret: str) -> str:
    """Return the lowercase hex HMAC-SHA256 of ``body`` under ``secret``."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Constant-time check of ``signature`` against the expected digest.

    Fails closed: garbage input (non-hex, empty, or non-ASCII)
    returns False instead of propagating.
    """
    try:
        expected: str = generate_signature(body, secret)
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False
