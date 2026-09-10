# Changelog — ugence-cloud-scaling-action-admission

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

## 0.1.0 — Phase 5C, initial release

- `capacity_action_to_canonical`: the fixed D-2 mapping from an envelope and a presented
  `ExecutionTargetScope` to a `CanonicalAction`.
- `CapacityActionGate`: Risk Authority's `ActionGatePort` for capacity actions, built per act,
  production-authoritative, `AUTHORIZED` or `DENIED` only.
- `CloudScalingActionAdmission`: fail-closed production and reference factories; `admit`
  builds one gate and one `ActionAdmissionSeam` per act.
- Neighbours unmodified: Risk Authority 0.8.0, Phase 5A 0.2.0, 5B-4 0.1.0.
