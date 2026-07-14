# ACP Cloud Domain Model (V2 §5)

Canonical cloud envelopes. Code:
`symbolu_robotics/autonomous_control_plane/cloud/envelopes.py`. All three reuse
the **frozen** `identity.identity` + `normalize_float` unchanged, with per-type
domain separation, so identities never collide across types or with robotics.

## `CloudWorldState` — domain `cloud_world_state`

Immutable cluster/deployment snapshot; `.version` is its content identity.

| field | type | meaning / source |
|---|---|---|
| `cluster`, `namespace`, `deployment` | str | K8s coordinates |
| `resource_version` | str | K8s `resourceVersion` (CAS token) |
| `generation` | int | `deployment.metadata.generation` |
| `desired_replicas` / `current_replicas` / `available_replicas` | int | replica counts |
| `readiness_plasticity` | float [0,1] | `cloud_controller` readiness signal |
| `active_rollback_watches` | int | open rollback watches (real `RollbackMonitor`) |
| `seconds_since_last_action` | float | cooldown input for real `ReadinessChecker` |
| `dependency_healthy` | bool | upstream dependency health |
| `freeze_active` | bool | real `BlackoutWindow` evaluated to a flag |
| `observation_time_s` | float | snapshot time |
| `extensions` | Mapping[str,str] | additive, identity-bearing |
| `provenance` | str | **identity-excluded** free-text label |

## `CloudActionCandidate` — domain `cloud_action_candidate`

A proposed operation. `.identity` is its content identity; `origin_state_version`
binds it to the state it was generated on (state/action binding).

`operation ∈ {SCALE, ROLLOUT, CONFIG_UPDATE, DELETE, ROLLBACK}`. Fields:
`current_replicas`, `desired_replicas`, `manifest_digest`, `rollback_ref`,
`rollout_strategy`, `max_unavailable`, `max_surge`, `timeout_s`, `metadata`,
`provenance` (identity-excluded). Derived properties:

- `blast_radius` — SCALE: `|desired − current|`; DELETE: `current` (all
  replicas); otherwise `max(max_surge, max_unavailable, 1)`.
- `is_destructive` — `operation is DELETE`.

## `CloudOperationalEvidence` — domain `cloud_operational_evidence`

Deterministic operational-safety evidence for one candidate, produced by the
evaluator (see `ACP_CLOUD_CONSTRAINTS.md`). `validity ∈ {VALID, STALE,
EVALUATOR_FAILED, MISSING}`; `is_usable` iff `VALID`. Carries `readiness_ok`,
`readiness_status`, `capacity_margin_replicas`, `rollback_available`,
`blast_radius`, `freeze_active`, `dependency_healthy`, `reason_codes`, and the
`candidate_identity` + `state_version` it binds to. `note` is identity-excluded.

## Grounding in real repository artifacts

- `deploy/gke/demo-app.yaml` — `demo-app`, ns `default`, `replicas: 3`,
  `nginx:1.25-alpine` (RollingUpdate) → `healthy_rollout`,
  `safe_constrained_rollout`.
- `deploy/gke/deployment.yaml` — `ncc-controller`, ns `ncc`, `replicas: 1` →
  `ncc_controller_scale`.
- `deploy/gke/configmap.yaml` — `max_scale_out_fraction 0.50`,
  `max_scale_in_fraction 0.25`, `min_replicas 1` → seed the real `SafetyConfig`.

## What is deliberately NOT modelled

Node-level scheduling/bin-packing, pod affinity, PDBs, HPA metrics, and live
Prometheus series are **not** modelled — the repository exposes no deterministic
source for them, and fabricating telemetry is forbidden. The envelopes carry only
fields the real `cloud_controller` logic or an explicit authored fixture can
populate.
