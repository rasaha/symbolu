# Pilot Preflight

> Before a pilot becomes READY, preflight verifies configuration, identity,
> allowlists, durable-store health + integrity, adapter/host/endpoint approval,
> read-only credential resolution (value never persisted), read-only GitHub
> permissions, known snapshot schemas, the execution-disabled invariant, a clean
> static write-boundary scan, and that evaluation/concurrency/stop bounds are
> present. It performs no mutation and prints no credential. Machine-readable
> companion: `docs/pilot_preflight_checks.json`.

## Outcomes

`PASS` · `PASS_WITH_WARNINGS` · `FAIL` · `NOT_RUN`. A `FAIL` on any check blocks
READY.

## Permission verification

Classified as `VERIFIED_FROM_SOURCE` (a live metadata GET succeeded),
`DECLARED_AND_VALIDATED` (declared read-only scopes validated), or `UNVERIFIED`.
The operator accepts only the minimum read permissions the actual endpoints need
and rejects any `*:write` scope. No GitHub-side permission is claimed cryptographic.
