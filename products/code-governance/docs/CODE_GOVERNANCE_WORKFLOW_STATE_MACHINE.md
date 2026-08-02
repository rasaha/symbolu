# Code Governance Workflow State Machine (MVP 1A — shadow)

> PRODUCT_INTERNAL, owned by the Workflow Service (which owns coordination, not
> governance authority). Machine-readable form: `docs/workflow_states.json`.
> Relationship to the design's canonical rungs: see
> `docs/audits/code_governance_readiness/STATE_MACHINE.md`.

## Forward path

```
RECEIVED -> IDENTITY_BOUND -> EVIDENCE_PENDING -> EVIDENCE_COMPLETE
  -> CLAIMS_EVALUATED -> ASSERTIONS_EVALUATED -> DECISION_PENDING
  -> DECISION_RECORDED -> CONTEXT_BOUND -> ACTION_PREPARED
  -> ACTION_EVALUATED -> SHADOW_COMPLETE
```

## Terminal / failure states (fail closed)

`SHADOW_COMPLETE` (success terminal), `STALE_ARTIFACT`, `CLAIMS_INCOMPLETE`,
`DECISION_REQUIRED`, `CHAIN_INCOMPLETE`, `BLOCKED`, `ESCALATED`, `ERROR`.

The machine **fails closed**: a stage requested from a state that does not permit
it raises `InvalidWorkflowTransitionError`; terminal states have no successors.

## Per-state contract

| State | Owner | Entry condition | Valid next | Fail behavior | Idempotency / retry |
|---|---|---|---|---|---|
| RECEIVED | Workflow Service | event ingested & normalized | IDENTITY_BOUND, ERROR | malformed event rejected before any state | same delivery id → same revision (idempotent) |
| IDENTITY_BOUND | Workflow Service | `GovernedChangeIdentity` bound | EVIDENCE_PENDING, STALE_ARTIFACT, ERROR | superseded head → STALE_ARTIFACT | re-ingest same head → same run |
| EVIDENCE_PENDING | Workflow Service | ≥1 current-head evidence admitted | EVIDENCE_COMPLETE, CLAIMS_INCOMPLETE, STALE_ARTIFACT, ERROR | stale evidence is stored but **not admitted** | admitting same evidence id is a no-op |
| EVIDENCE_COMPLETE | Workflow Service | Claim Manifest built | CLAIMS_EVALUATED, CLAIMS_INCOMPLETE, ERROR | — | manifest is content-addressed |
| CLAIMS_EVALUATED | Workflow Service (policy) | mandatory gate satisfied (non-compensatory) | ASSERTIONS_EVALUATED, BLOCKED, ERROR | mandatory incomplete/unsatisfied → CLAIMS_INCOMPLETE | evaluation is pure |
| ASSERTIONS_EVALUATED | TAP (via WS) | per-claim assertion results recorded | DECISION_PENDING, CHAIN_INCOMPLETE, ERROR | missing TAP result → CHAIN_INCOMPLETE at finalize | evaluation deterministic |
| DECISION_PENDING | Workflow Service | decision requested | DECISION_RECORDED, DECISION_REQUIRED, BLOCKED, ESCALATED, ERROR | **no authorized actor → DECISION_REQUIRED** | — |
| DECISION_RECORDED | Decision Authority | authorized actor recorded `DecisionRecord` | CONTEXT_BOUND, ERROR | deny outcome → BLOCKED (no action prep) | DA record immutable |
| CONTEXT_BOUND | Decision Authority (CER) | `cer.v1` CER bound to the decision | ACTION_PREPARED, ERROR | — | CER content-hashed |
| ACTION_PREPARED | Workflow Service | `PreparedMergeAction` built | ACTION_EVALUATED, ERROR | — | content-derived fingerprint |
| ACTION_EVALUATED | ActionGate (shadow) | `ActionGovernanceResult` recorded SHADOW_ONLY | SHADOW_COMPLETE, CHAIN_INCOMPLETE, ERROR | any missing chain link → CHAIN_INCOMPLETE | shadow result never acted on |
| SHADOW_COMPLETE | Workflow Service | complete chain reconstructable | — (terminal) | — | revision snapshot persisted once |

## Head-SHA invalidation (§20)

A new synchronization event that changes `head_sha` produces a **new revision**
under the same workflow lineage (`workflow_id` stable; `revision_id` bound to
base/head). Prior evidence, manifest, TAP results, recommendation, decision, CER,
prepared action, and ActionGate result are **not** reused for the new head — they
remain reconstructable but non-current (`STALE` on reconstruction). Historical
records are never mutated.

## Mode

The only mode is `SHADOW` (`WorkflowMode.SHADOW`). There is no
`AUTHORIZATION_ISSUED`, `CLEARANCE`, `DISPATCHING`, or `MERGED` state in this
phase; execution is disabled.
