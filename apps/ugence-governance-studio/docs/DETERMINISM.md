# Governance Studio API — Determinism (P3B)

For identical logical inputs: AWC outputs, result fingerprints and canonical
ordering are identical; scenario exports are stable; process restart and
concurrent requests do not change results. `request_id` and server timing never
affect domain results (verified by the concurrency + determinism suites and by
separate-process checks in the distribution verifier).

The API adds a canonical JSON serializer for presentation only. It never
re-canonicalizes AWC objects in a way that changes their meaning or fingerprints;
serialization mirrors AWC's own `model_dump(mode="json")` projection, so built-in
scenarios reproduce the frozen fingerprints byte-for-byte.

Logical time is a pinned scenario input (`1_000_000.0`), not runtime state.
