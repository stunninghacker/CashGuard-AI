"""External-system adapters (Tier 2 integration point).

Each adapter wraps a real external API behind a common, testable interface.
`LIVE` config flags default to False — the prototype stays simulated until a
real credential/endpoint is configured (honest, no fabricated live calls).
"""
