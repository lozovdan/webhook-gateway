"""Integration tests for GET /donations and GET /donations/{event_id}.

Planned cases:
    - Empty store: GET /donations -> 200 with an empty list.
    - After ingesting N events: GET /donations -> 200 with N items in order.
    - GET /donations/{event_id} for an existing id -> 200 with that event.
    - GET /donations/{event_id} for an unknown id -> 404.
    - Response shape matches the public model (no secret/internal fields leak).
"""

# TODO: implement the cases above
