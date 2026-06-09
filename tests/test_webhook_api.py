"""Integration tests for POST /webhooks/donation.

Planned cases:
    Happy path:
        - Valid payload + valid signature -> 200, body echoes/acknowledges,
          and the event becomes retrievable via GET /donations/{id}.

    Bad payload -> 400 (parametrized over distinct violations):
        - negative amount, zero amount, unknown currency,
          each missing required field, malformed timestamp.
        - NOTE: payload must still carry a *valid* signature so we isolate the
          400 (validation) path from the 401 (auth) path.

    Bad signature -> 401:
        - missing X-Signature header.
        - wrong signature value.
        - signature valid for a *different* body (tampered payload).

    Duplicate event_id -> 409 (idempotency):
        - same event_id twice -> first 200, second 409.
        - the donation is stored exactly once (verify via GET /donations).
"""

# TODO: implement the cases above (use @pytest.mark.parametrize for negatives)
