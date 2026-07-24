# Governed Request & Response Schema (Phase 2)

*`governed_inference_pilot/schema.py`. `GovernedRequest` (`gip_request_v1`) is the canonical input to
the runtime; `ResponseEnvelope` (`gip_envelope_v1`) is the canonical output. The envelope preserves
every stage-local outcome — the final shadow disposition never erases the underlying stage decisions.*

## GovernedRequest (fields)

Identity & routing: `request_id`, `tenant_id`, `session_id`, `user_role`, `task_type`, `domain`,
`risk_tier` (low/medium/high/critical), `jurisdiction`.

Prompt & policy: `user_prompt`, `system_constraints`, `enterprise_policy_refs`, `policy_version`,
`data_sensitivity`, `requested_output_form`.

Model-selection inputs: `acceptable_quality_threshold`, `cost_constraint_usd`, `latency_constraint_ms`,
`provider_restrictions`, `allowed_models`, `prohibited_models`.

Governance inputs: `evidence_requirements`, `citation_requirements`, `action_permissions`,
`human_review_required`.

Execution & provenance: `execution_mode` (fixture/recorded/opt_in_local — **default fixture**),
`source_artifact_ref`, `timestamp` (fixed value; no wall-clock, for determinism), `expected_labels`
(ground-truth, where available).

## ResponseEnvelope (fields)

`request_id`, `final_shadow_disposition` (one of the 11 shadow outcomes), `stage_events` (the immutable
per-stage record), `stage_dispositions` (stage → its local disposition, **never collapsed**),
`reason_codes`, `claims`, `evidence_states`, `action_disposition`, `human_review_state`,
`uncertainties`, `total_latency_units`, `estimated_cost_usd`, `replay_signature`, `envelope_version`.

## Design commitments

- **Determinism:** `timestamp` is a fixed field, never `now()`; latency is measured in deterministic
  *units* (Phase 20), not wall-clock, so the corpus and traces reproduce byte-for-byte.
- **No erasure:** `stage_dispositions` retains each stage's own decision alongside the single
  `final_shadow_disposition`. An operator can always see *why* the final outcome arose from the stages.
- **Fixture honesty:** `execution_mode` records whether a real model ran; the default is `fixture`, and
  the envelope never implies a live model ran when a fixture was used.
