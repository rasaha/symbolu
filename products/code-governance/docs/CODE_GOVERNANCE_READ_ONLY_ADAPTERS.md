# Read-Only Enterprise Adapters

> Every adapter is **strictly read-only** and produces **data only** — an
> `AdapterResult`. An adapter never authorizes, approves, merges, executes, or
> mutates a workflow or an external system. Machine-readable companion:
> `docs/adapter_capabilities.json`.

## The narrow contract

```python
adapter.capability() -> AdapterCapability
adapter.collect_snapshot(request: AdapterRequest) -> AdapterResult
```

`AdapterRequest` binds the exact governed change (tenant, workflow, revision,
repository, PR number, base/head SHA, target branch, prepared-action fingerprint,
ActionGate authorization fingerprint, requested signal types, caller-supplied
collection time, source config ref). `AdapterResult` is data only: adapter/source
identity, requested signal types, collected facts, `captured_at`/`valid_until`,
`fetch_status`, `failure_codes`, provenance, and a read-only guarantee. **Neither
model carries a credential.**

## Read-only transport boundary

`ReadOnlyTransport` permits only GET (and HEAD when the policy enables it). It
rejects every mutating method (POST/PUT/PATCH/DELETE/OPTIONS/TRACE) and GraphQL
mutations (all POST), enforces host and path allowlists, bounded timeouts, bounded
response sizes, content-type validation, and validates every redirect target
against the allowlist. Violations raise `ReadOnlyBoundaryViolation` /
`AdapterResponseError`. No adapter may bypass the boundary with a private client.

## Fact consistency

Collected facts are classified `AUTHORITATIVE`, `EVENTUALLY_CONSISTENT`,
`ADVISORY`, or `UNAVAILABLE`, so downstream normalization can treat an
eventually-consistent GitHub check differently from an authoritative artifact
identity.

## Failure handling (fail closed)

A source failure is a structured `AdapterFailureCode` and **never** a positive
signal. A failed collection yields a fact-free `FAILED` result; the resulting
missing/unknown signal makes the clearance evaluation non-CLEAR. Retries are
bounded and only for safe reads; identity/schema/boundary failures are never
retried. Conflicting facts for one signal type are marked unknown and recorded as
conflicts (fail closed; typically routed to a non-CLEAR outcome).

## Normalization

`normalize_results` combines adapter results into the existing
`CodeGovernanceOperationalSnapshot` + `TrustedSignalSourceProjection`, which feed
the *unchanged* MVP 1B clearance path. Adapters therefore add a read-only signal
front-end without touching Action Clearance, ActionGate, or the workflow machine.
