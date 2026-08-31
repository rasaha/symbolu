# Audit Trace Specification (Phase 5)

*`governed_inference_pilot/audit.py` (`gip_audit_v1`). The trace is a list of **immutable event
records**, one per attempted stage, plus request/version metadata and a deterministic replay signature —
not merely a final summary.*

## AuditTrace

`trace_id`, `parent_trace`, `request_snapshot`, `source_artifact_hashes`, `component_versions`,
`policy_versions`, `events[]`, `final_shadow_disposition`, `human_review_state`, `replay_signature`.

## AuditEvent (per stage, append-only)

`seq`, `stage`, `component_version`, `disposition` (stage-local), `shadow_outcome` (mapped),
`reason_codes`, `source_repr`, `transformed_repr`, `semantic_loss`, `missing_metadata`, `claim_refs`,
`evidence_refs`, `action_refs`, `latency_units`, `cumulative_latency_units`, `estimated_cost_usd`,
`error`. Events are added via `add()`, which stamps `seq` and cumulative latency — records are never
mutated after insertion.

## Deterministic replay signature

`compute_signature()` hashes the **decision-bearing** content only — request snapshot, and per event
the stage, local disposition, shadow outcome, reason codes, and semantic loss — **excluding** latency
and cost. This means:

- the signature reproduces byte-for-byte across runs (no wall-clock, no cost noise);
- replay (Phase 6) can detect **decision drift** independent of instrumentation drift — a change in
  latency does not change the signature, but a change in any disposition does.

## Views

- **Operator view** (`view(internal=False)`): redacts `source_repr` / `transformed_repr` (which may
  contain raw component internals), showing dispositions, reasons, refs, latency, and cost.
- **Internal view** (`view(internal=True)`): the full record including source/transformed
  representations, for engineering diagnosis and semantic-loss verification.

## Completeness

`audit_complete()` is true only when there is at least one event, a final disposition, and a signature.
The evaluation (Phase 18) reports audit completeness on all non-catastrophic runs; a run that produced
no complete audit is itself a finding.

## Immutability & provenance

The trace stores `source_artifact_hashes` (of the model output / fixtures) and `component_versions` /
`policy_versions`, so any later replay can prove it ran against the same inputs and the same frozen
component versions. Event records are the ground truth; the final summary is derived from them, never
the reverse.
