# Code Governance MVP 1B — Implementation

> **Read-only and non-enforcing.** MVP 1B integrates the **canonical Action
> Clearance capability** (`ugence_action_clearance`, PR #1280) into the Code
> Governance shadow workflow (`ugence_code_governance`, PR #1279) as a **shadow-only
> stage**, and adds deterministic, explainable human-intervention routing.
> Execution remains disabled: no GitHub write path, no merge credential, no
> execution provider, no reservation, no production database.

## The extended chain

```
GitHub change identity -> evidence -> Claim Manifest -> TAP -> DecisionRecord
  -> ContextEnvelopeRecord -> PreparedMergeAction -> ActionGate shadow authorization
  -> Action Clearance shadow evaluation           (NEW)
  -> explainable human-intervention assessment     (NEW)
  -> complete governance-chain reconstruction
  -> EXECUTION_DISABLED
```

It answers: *does this exact, already-authorized change remain operationally clear,
and does the current condition require additional human intervention?*

## Authority boundary preserved

- **ActionGate** authorization is required **before** Action Clearance evaluation;
  only `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS` are eligible. An ineligible/denied
  outcome records `NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED` — never a fabricated CLEAR.
- **Action Clearance** never authorizes execution; `CLEAR` is not execution.
- The existing **DecisionRecord** remains the binding governance decision. The new
  `HumanInterventionAssessment` is advisory/routing metadata (`is_binding = False`) —
  never a `DecisionRecord`.
- No package was modified except `products/code-governance/`. The canonical Action
  Clearance package is composed through its **public API only**.

## What was added (all under `products/code-governance/`)

| Module | Role |
|---|---|
| `clearance/adapter.py` | `ActionClearanceShadowAdapter`: ActionGate result + PreparedMergeAction -> canonical `AuthorizationContext` / `AuthorizedActionIdentity` / `ClearancePolicyContext` / `ClearanceRequest` |
| `clearance/snapshot.py` | `CodeGovernanceOperationalSnapshot`: supplied, offline operational facts (no live clients) |
| `clearance/source_projection.py` | `TrustedSignalSourceProjection`: immutable approved-source registry projection |
| `clearance/signal_adapter.py` | `build_trusted_signals`: snapshot -> canonical `TrustedSignal` (fail-closed on unapproved source/version/trust) |
| `clearance/profile.py` | `CodeGovernanceClearanceProfile`: narrow company policy projection -> canonical `ClearancePolicy` |
| `clearance/records.py` | `ActionClearanceEvaluationRecord`: immutable shadow evaluation record (not a receipt) |
| `clearance/intervention.py` | `InterventionType`, `InterventionRoutingPolicy`, `HumanInterventionAssessment`, `assess_intervention` |

Workflow states, the governance-chain record, reconstruction, and the public API
were extended in a backward-compatible way (MVP 1A behavior is unchanged;
`evaluate_action_shadow(..., finalize=True)` is the default 1A path).

## Determinism

All product fingerprints are content-derived; `evaluation_time` is caller-supplied
(no clock read). The clearance evaluator/adapter are pure functions: identical
authorization inputs + identical signals + identical evaluation time yield identical
signal/request/result/intervention fingerprints. The upstream DA-minted CER carries a
wall-clock `issued_at`/`content_hash`, so two independent full-pipeline DA runs differ
in the CER hash (documented provenance); determinism is proven at the evaluator/adapter
level with fixed inputs.

## Tests & demo

- `products/code-governance/tests/` — 127 tests (65 MVP 1A + 62 new 1B).
- `examples/clearance_shadow_demo.py` — deterministic, offline, fixture-only demo of
  CLEAR/HOLD/BLOCK/ESCALATE, head-SHA staleness, and identical-replay fingerprints.

See the companion docs and machine-readable artifacts in this directory.
