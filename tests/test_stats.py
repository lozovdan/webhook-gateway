"""Integration tests for GET /stats (aggregation correctness).

Planned cases:
    - Empty store: count == 0 and empty per-currency breakdown.
    - Single donation: totals reflect that one event.
    - Multiple donations, same currency: total == sum, count == N.
    - Multiple currencies: each currency aggregated independently.
    - Decimal precision: sums do not lose precision (e.g. 0.1 + 0.2).
    - Duplicates (same event_id) are counted once (ties into idempotency).
"""

# TODO: implement the cases above
