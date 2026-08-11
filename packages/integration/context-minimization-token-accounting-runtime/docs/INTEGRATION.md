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
