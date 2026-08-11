# Integration Guide — CM-TA1

## The flow

```
MinimizationResult ──prepare_api_call_measurement──▶ PreparedApiCall  (A: context, B: estimate)
                                                          │  register(instance_id, task_id)
AgentRuntime ──attempt_observer──▶ RuntimeTokenAccountingBridge
   provider.execute (per attempt) ─▶ ProviderAttempt (neutral, opaque usage)
                                          │  translate_attempt(prepared, attempt, normalizer)
                                          ▼
                        ApiCallTokenRecord ──▶ TokenAccountingSink
                                          │
             aggregate_logical_request_usage ─▶ LogicalRequestTokenSummary
                                          │
                 settle_budget_from_usage / _from_summary ─▶ H22-D BudgetCoordinator
```

## Steps

1. **Minimize** context with the Context Minimization core → a `MinimizationResult`
   (measurement A).
2. **Prepare** a per-logical-request measurement:
   `prepare_api_call_measurement(minimization_result=..., logical_request_id=..., provider_id=..., request_components=...)`.
   This copies A verbatim and produces the complete-request estimate (B) — via an injected
   `RequestTokenCounter` or the default approximate counter.
3. **Register** the prepared measurement on the bridge keyed by the runtime identity its
   attempts will carry: `bridge.register(prepared, instance_id=..., task_id=...)`.
4. **Drive** the runtime with `attempt_observer=bridge`. Each actual `provider.execute`
   emits a `ProviderAttempt`; the bridge translates it (measurement C via the injected
   `UsageNormalizer`) into an `ApiCallTokenRecord` and records it. A governance
   HOLD/BLOCK/ESCALATE or exact-action rejection never invokes the provider → no record.
5. **Aggregate** with `aggregate_logical_request_usage(sink.records)` and **settle** the
   H22-D budget at the quantum boundary with `settle_budget_from_usage(...)` (per attempt's
   authoritative usage) or `settle_budget_from_summary(...)` (from the complete summary).

## Budget settlement semantics

- **Measured** — authoritative usage yielding a token-unit magnitude (reported
  `total_tokens`, else derived `input + output`) settles the actual amount
  (`actual_known=True`) and releases the unused reservation.
- **Conservative** — no usage, or no derivable magnitude, falls back to charging the full
  reservation (`actual_known=False`) — never under-charging.
- **Overrun** — a measured value above the reservation raises `BudgetEstimateExceeded` from
  the coordinator; it is surfaced, never clamped. The reservation is left intact for the
  caller to release explicitly.

## Injecting a real provider adapter

`MappingUsageNormalizer` is a mechanical helper for simple key renames. A real vendor
adapter implements the `UsageNormalizer` protocol (`normalize(neutral_usage) ->
ProviderTokenUsage | None`) and lives **outside** this package so no vendor SDK enters the
base install. It must never invent counts the provider did not report — returning `None`
records the attempt as usage-unavailable, not zero.

## Attempt identity (F3)

`translate_attempt` derives a deterministic, collision-resistant `attempt_id` bound to the
FULL logical-request identity (`prepared.logical_request_id` + `instance_id` + `task_id` +
`attempt_number`), using a length-prefixed encoding so no two distinct identity tuples can
collide regardless of id contents. Missing, empty, or whitespace-only identity is **rejected**
(no placeholder fallback), so two distinct logical requests can never share an attempt id
merely because instance/task identity is absent. No wall-clock, no randomness, and no
provider-controlled request id is used as internal attempt authority.

Retry linkage never crosses identity schemes: when `attempt_id` is **derived**, its
`retry_of_attempt_id` is derived from the **same** scheme (the attempt-(n-1) id). When an
`attempt_id` is supplied **explicitly**, the derivation scheme is never used to reconstruct
retry linkage — a retry then **requires** an explicit `retry_of_attempt_id`, a non-retry must
not carry one, and supplying `retry_of_attempt_id` while deriving the id is rejected.

## Settlement field (F1)

`settle_budget_from_summary` charges `summary.settlement_token_units` (the documented
per-attempt reported-else-derived selection) — **not** `provider_reported_total_tokens`, which
by contract holds only provider-reported values and would understate consumption when an
attempt reported input/output but no explicit total. It settles only when the summary is
`complete`; an incomplete summary falls back to conservative full-reservation settlement.

## Concurrency (F4)

The reference `InMemoryTokenAccountingSink` is thread-safe (atomic duplicate-detect-and-insert;
consistent snapshots), and the bridge's `skipped_attempts` diagnostic is lock-protected against
lost increments. The per-attempt (`settle_budget_from_usage`) and summary
(`settle_budget_from_summary`) settlement paths target the same H22-D reservation, which the
coordinator settles exactly once (the second call finds no active hold and is a no-op) — so the
same reservation is never charged twice. Thread-safe in-memory storage is **not** durable
storage; production persistence remains follow-on work.

## Tenant isolation (N1)

Attempt-id derivation is tenant-scoped. `translate_attempt` takes the tenant from
`prepared.attribution.tenant_id` and binds the canonical tenant namespace
(`canonical_tenant_namespace`) as a prefix-free segment of the derived `attempt_id`, so two
tenants using **identical** tenant-local ids (`logical_request_id` + instance + task +
attempt_number) derive **different** attempt ids. A derived retry's `retry_of_attempt_id`
uses the **same** tenant namespace, so retry chains never cross tenants. `derive_attempt_id`
accepts an explicit `tenant_id` (absent → the single-tenant namespace `"s"`; present → must be
non-empty/non-whitespace).

Defense in depth: the reference `InMemoryTokenAccountingSink` additionally partitions
idempotency/conflict detection by `(tenant_namespace, attempt_id)`, so even **explicit**
`attempt_id` overrides cannot collide across tenants. Callers sharing accounting infrastructure
across tenants MUST populate `RequestAttribution.tenant_id`.
