# Changelog — ugence-cloud-scaling-bounded-execution

## Unreleased

- Pin raised to Cloud Scaling Operations `>=0.2.0` (orchestrator containment ruling); the
  import-boundary test's forbidden operations set gains `action.k8s_actuator`,
  `action.gate_actuator` and `recommend`. No code change.

## 0.1.0 — Phase 5D, initial release

- `BoundedExecutionSeam` with production/reference factories: the only path from a
  `CredentialGrant` to `ControlledScalingExecutor.execute` (D-1, D-2).
- `resolve_effective_mode` and `LivePosture`: LIVE only under a proven posture, any absence
  resolving to `dry_run` (D-3).
- `narrow_target_policy`: ceilings and allowlists from the grant's role, never wider than
  config; rollback refused on a bare policy (D-4).
- `BoundedExecutionRecord` and `effect_observation_for` for RA-8; the reservation advanced at
  dispatch and at observation (D-5).
- Neighbours unmodified: Cloud Scaling Operations 0.1.2, credential-broker 0.1.0,
  execution-reservation 0.1.0, Risk Authority 0.8.0.
