# Canonical Decision Record Specification (v1)

*Phase 6. One append-only, hash-chained record format able to represent **every**
control-plane decision — eligibility, selection, provider execution, assertion,
action, telemetry. Implemented in `control_plane/decisions.py` (`DecisionRecord` +
`AuditLog`).*

## Purpose

A single record shape lets one audit log carry decisions from seven different
components without a per-component schema. It supports six consumers:

| Consumer | What it needs from the record |
|---|---|
| Deterministic replay | pinned `policy_version` + `registry_version` + `input_ref` + `output_state` |
| Causal tracing | `trace_id` + `prior_record_hash` chain + ordered components |
| Independent component evaluation | `component` + `reason_codes` scoped to that component's namespace |
| Conflict investigation | `selected_candidate` / `excluded_candidates` / `assertion_disposition` / `action_disposition` |
| Audit reconstruction | `record_hash` chain + `verify_chain()` |
| Redacted external review | confidential fields redacted before persistence |

## Fields

R=required · O=optional-per-decision-type · IM=immutable once written · C=confidential (redacted in artifacts).

| Field | Class | Meaning |
|---|---|---|
| `decision_id` | R, IM | unique per decision |
| `request_id` | R, IM | the enterprise request |
| `trace_id` | R, IM | spans the whole lifecycle |
| `component` | R | which component made the decision (one of the 8 layers) |
| `component_version` | R | pinned component version (replay fidelity) |
| `decision_type` | R | eligibility / selection / execution / assertion / action / telemetry |
| `input_ref` | R | reference/hash to the input (never raw payload) |
| `output_state` | R | the component's typed state (e.g. `ELIGIBLE`, `APPROVE`, `DENY`) |
| `reason_codes` | R | namespaced codes (`EXEC.*`/`MODEL.*`/…); ≥1 for any non-nominal outcome |
| `evidence_refs` | O | source references cited for the decision |
| `evidence_timestamps` | O | for staleness/TTL evaluation |
| `policy_version` | R, IM | pinned per trace |
| `registry_version` | R, IM | pinned per trace |
| `confidence` | O | where a component produces one (e.g. assertion) |
| `human_authority_ref` | O, C | attributable approver reference (not PII) |
| `override_status` | R | `none` / `applied` |
| `override_actor` | O, C | who overrode (attributable) |
| `override_rationale` | O | why (audited) |
| `latency_ms` | O | this decision's latency |
| `projected_cost_usd` | O | pre-execution estimate |
| `observed_cost_usd` | O | post-execution actual (telemetry) |
| `selected_candidate` | O | for selection decisions |
| `excluded_candidates` | O | with the reason they were excluded |
| `assertion_disposition` | O | APPROVE/QUALIFY/CONSTRAIN/ESCALATE/REJECT |
| `action_disposition` | O | ALLOW/DENY/APPROVE_REQUIRED/CONSTRAIN/ESCALATE/INDETERMINATE |
| `execution_outcome` | O | observed outcome (enforcement/telemetry) |
| `prior_record_hash` | R, IM | hash of the previous record in the log |
| `record_hash` | R, IM | sha256 over the record body (excl. `record_hash`) + `prior_record_hash` |

## Integrity model

- **Hash chain.** `record_hash = sha256(sorted_json(body \ record_hash) + prior_record_hash)`.
  `AuditLog.append()` sets `prior_record_hash` to the running head, computes the hash over
  the **redacted** payload, appends, and advances the head. `verify_chain()` recomputes every
  link; any tampering or reordering breaks it → `AUDIT.AUDIT_CHAIN_BROKEN`.
- **Append-only.** No update/delete API. Telemetry cannot rewrite a prior record (invariant 11);
  corrections are new prospective records (invariant 12).
- **Fail-closed writes.** A write failure raises (`AUDIT.TELEMETRY_WRITE_FAILED`); in ENFORCEMENT
  mode where policy requires traceability, this blocks execution (invariant 15).

## Redaction (no raw content by default)

`AuditLog` redacts any key matching secret patterns (`api_key`, `authorization`, `token`,
`secret`, `password`, `bearer`) before hashing/persisting. Confidential fields
(`human_authority_ref`, `override_actor`, tenant references) are redacted in externally-shared
artifacts. Raw prompt/response content is **never** stored by default — only `input_ref` /
`evidence_refs` (invariant 16, and Phase 13 content-minimization).

## Per-decision-type population (illustrative)

| decision_type | key populated fields |
|---|---|
| eligibility | `output_state` (ELIGIBLE/…), `excluded_candidates`, `evidence_refs`, `evidence_timestamps` |
| selection | `selected_candidate`, `excluded_candidates`, `projected_cost_usd`, cites eligibility `decision_id` via `input_ref` |
| execution | `execution_outcome`, `observed_cost_usd`, `latency_ms`, RUNTIME.* reason on failure |
| assertion | `assertion_disposition`, `confidence`, ASSERT.* reason |
| action | `action_disposition`, `human_authority_ref`, `override_*`, ACTION.* reason |
| telemetry | `observed_cost_usd`, `execution_outcome`, prospective-only |

## Replay contract

Replay reconstructs a trace using the **historical** `policy_version` + `registry_version`
recorded in each record (invariant 13). A replay whose pinned versions differ from the
record's → `POLICY.REPLAY_VERSION_MISMATCH`. Replay is read-only: it never emits telemetry
or registry updates.
