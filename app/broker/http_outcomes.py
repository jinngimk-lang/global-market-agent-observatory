from __future__ import annotations

AMBIGUOUS_MUTATION_HTTP_STATUSES = frozenset({408, 429})


def is_ambiguous_mutation_http_status(status_code: int) -> bool:
    """Return True when a mutation response does not prove broker non-execution.

    HTTP 408 and 429 can be produced around proxy/gateway/rate-limit boundaries
    after a request has already been transmitted. Treating them as a definite
    rejection can make a later retry duplicate an order or cancellation.
    Server-side 5xx responses are handled by each adapter's existing UNKNOWN
    branch so their established result codes remain stable.
    """

    return status_code in AMBIGUOUS_MUTATION_HTTP_STATUSES
