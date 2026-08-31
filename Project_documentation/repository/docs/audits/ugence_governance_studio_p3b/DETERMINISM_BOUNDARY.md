# Determinism Boundary (P3B)

Logical results depend only on pinned inputs + injected logical time. Excluded
from logical fingerprints: `request_id`, server timestamps, process identity,
request ordering. The presentation-only canonical serializer mirrors AWC's
`model_dump(mode="json")` and never alters AWC fingerprints. Built-in scenarios
reproduce the frozen oracles byte-for-byte across processes (verified by the
determinism/concurrency suites and the isolated distribution verifier).
