"""Unit tests for app.models (Pydantic validation).

Planned cases:
    Happy path:
        - A fully valid payload parses into a DonationEvent.
        - currency is normalised to uppercase.
        - amount accepts typical positive values (int/str/Decimal forms).

    Negative (parametrized):
        - amount == 0 is rejected.
        - amount < 0 is rejected.
        - currency outside the allowlist is rejected.
        - each required field missing (event_id, donor, amount, currency,
          timestamp) is rejected with a clear error.
        - malformed timestamp is rejected.
        - wrong types (e.g. amount = "abc") are rejected.
"""

# TODO: implement the cases above (use @pytest.mark.parametrize for negatives)
