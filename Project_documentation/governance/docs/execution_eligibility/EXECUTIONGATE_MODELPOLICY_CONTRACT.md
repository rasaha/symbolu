# ExecutionGate ↔ ModelPolicy Integration Contract

*Phase 6 deliverable. The strict interface between "can execute" (ExecutionGate) and
"should execute" (ModelPolicy). Implemented across `gate.py`, `registry.py`, `policy.py`.*

## Boundary

- **ExecutionGate** emits `EligibilityDecision`s. It **never** ranks or picks a preferred
  model among eligibles.
- **ModelPolicy** consumes only ExecutionGate output + normalized capability/cost/operational
  metadata. It **never** interprets raw provider error strings, and it **never** selects an
  INELIGIBLE or INDETERMINATE candidate.

## Input to ModelPolicy (from ExecutionGate / registry)

```
{
  eligible:      [ {record, decision(state=ELIGIBLE), quality_prior, cost_meta, op_meta} ],
  conditional:   [ {record, decision(state=CONDITIONALLY_ELIGIBLE), ..., degraded_reasons} ],
  excluded:      [ {record, decision(state INELIGIBLE|INDETERMINATE), reasons:[ReasonCode], evidence_ts} ],
  policy_version, evaluated_at
}
```

- `excluded` carries **reason codes**, not raw strings — so ModelPolicy's logs and any
  operator UI are provider-neutral and auditable.
- ModelPolicy may consider `conditional` only when its config `allow_conditional=true`, and
  must rank them below `eligible`.

## Output from ModelPolicy

```
{ selected: record | null, ranked: [(record, utility)], abstained: bool, reason }
```

- `abstained=true` when the eligible+conditional pool is empty (fail fast; do **not**
  attempt an ineligible model).

## Error / timeout / staleness / indeterminate behavior

| Situation | ExecutionGate behavior | ModelPolicy behavior |
|---|---|---|
| A probe times out | condition → UNKNOWN with `TELEMETRY_STALE`/`POLICY_STATE_UNKNOWN`; criticality decides state | receives the resulting state; never sees the timeout directly |
| Evidence past TTL | condition degrades to UNKNOWN (not last value) | candidate may drop to INDETERMINATE/INELIGIBLE and is excluded |
| Critical-GOV unknown | fail-closed → INELIGIBLE | excluded; cannot be resurrected by high utility |
| Whole pool INDETERMINATE | — | abstain and signal "resolve evidence" (do not guess) |
| Conflicting evidence | resolve by fixed source precedence; loser retained for audit | unaffected (sees resolved decision) |

## Audit requirements

Every routed request produces a decision record containing: the request fingerprint, the
gate `policy_version`, per-candidate `EligibilityDecision` (state + reason codes + evidence
timestamps), the ModelPolicy ranking + selected model, and the abstain reason if any. Raw
provider strings live only inside evidence, never in the selection logic.

## Version compatibility

- `policy_version` is stamped on every decision. ModelPolicy checks it is a known version;
  an unknown gate version ⇒ ModelPolicy treats all candidates as INDETERMINATE (fail-safe),
  never as eligible.
- Reason codes are append-only; a ModelPolicy that receives an unknown code treats the
  candidate as excluded (fail-closed), never eligible.

## The one invariant that defines the boundary

> **ModelPolicy can only ever choose from what ExecutionGate declared executable. If
> ExecutionGate is wrong in the unsafe direction (false-eligible), ModelPolicy inherits that
> error — which is why false-eligibility on critical constraints is weighted more severely
> than false-ineligibility in the evaluation.**
