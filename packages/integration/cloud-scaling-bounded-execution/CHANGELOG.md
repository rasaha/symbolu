# Changelog — ugence-cloud-scaling-bounded-execution

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

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
