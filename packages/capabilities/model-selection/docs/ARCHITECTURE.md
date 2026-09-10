# Architecture

## Three stages, in one direction

```
Approved candidate set  (ExecutableRegistry)
        │
        ▼
ExecutionGate      mandatory eligibility — fail-closed, non-compensatory, never ranks
        │
        ▼
Eligible candidate set
        │
        ▼
ModelPolicy        deterministic weighted ranking — only ever over the eligible set
        │
        ▼
ModelAuthority     binding decision: ALLOW / DENY / HOLD / ESCALATE (+ governed fallback)
```

Each arrow is one-way. Ranking cannot reach back into eligibility, and authorization
cannot reach past ranking into a candidate the gate rejected.

## Modules

| Module | Owns |
|---|---|
| `states.py` | `EligibilityState`, `Verdict`, `Criticality`, `Evidence`, `ConditionResult`, `EligibilityDecision`, and the fixed `SOURCE_PRECEDENCE`. |
| `reason_codes.py` | The append-only `ReasonCode` taxonomy and `normalize_raw`. Raw provider strings live in `Evidence`, never as codes. |
| `model.py` | `Request`, `Candidate`, `Signal`, `GateConfig` — the inputs, including `quality_floor` and its validation. |
| `gate.py` | The sixteen eligibility conditions and the fixed aggregation precedence. |
| `policy.py` | `PolicyWeights`, `select` — the utility function and the eligible-set filter. |
| `authority.py` | `ModelAuthority`, the disposition vocabulary, and the governed fallback chain. |
| `registry.py` | `ModelRecord`, `ExecStatus`, `ExecutableRegistry` — candidate metadata and execution-verification lineage. |
| `fingerprint.py` | Stable SHA-256 over canonical JSON of an already-produced record. Adds no behaviour. |
| `api.py` | The curated public surface. Re-exports only; no logic. |

## Criticality classes and what they mean

| Class | Conditions | On FAIL | On UNKNOWN |
|---|---|---|---|
| `CRITICAL_GOV` | network policy, region, data residency, enterprise approval | INELIGIBLE, unconditionally | INELIGIBLE |
| `CRITICAL_OP` | reachability, authentication, credential expiry, billing, model availability, features, context length, projected cost, **capability floor** | INELIGIBLE | INELIGIBLE, unless the condition is in `indeterminate_on_unknown` → INDETERMINATE |
| `OPERATIONAL` | quota, latency, reliability/degradation | INELIGIBLE | CONDITIONALLY_ELIGIBLE if `allow_conditional`, else INELIGIBLE |

Only `OPERATIONAL` is configurably soft, and only into CONDITIONALLY_ELIGIBLE, which
ranking penalizes (`PolicyWeights.conditional_penalty`) rather than ignores.

## Evidence and time

Every operational fact arrives as a `Signal` carrying `Evidence`: a source, a timestamp, a
confidence and a TTL. Stale evidence degrades to UNKNOWN and the last value is **not**
retained — `_resolve` returns `None` rather than the expired reading.

`now` is a parameter everywhere; nothing reads a system clock. That is what makes a
decision replayable, and `test_the_package_reads_no_system_clock` enforces it by scanning
for `time.time` / `datetime.now` / `datetime.utcnow` across the source.

A decision's `ttl_seconds` is the *minimum* TTL across the evidence it cited, so the
decision expires with its shortest-lived input.

## Determinism

For fixed `(candidate, request, config, now)` the decision record is byte-identical across
repeated calls and fresh instances, and so is its fingerprint. Ranking sorts on
`(-utility, internal_id)`, so ties break on a stable identifier rather than on registry
insertion order.
