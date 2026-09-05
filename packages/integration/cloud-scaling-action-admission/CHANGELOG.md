# Changelog — ugence-cloud-scaling-action-admission

## 0.1.0 — Phase 5C, initial release

- `capacity_action_to_canonical`: the fixed D-2 mapping from an envelope and a presented
  `ExecutionTargetScope` to a `CanonicalAction`.
- `CapacityActionGate`: Risk Authority's `ActionGatePort` for capacity actions, built per act,
  production-authoritative, `AUTHORIZED` or `DENIED` only.
- `CloudScalingActionAdmission`: fail-closed production and reference factories; `admit`
  builds one gate and one `ActionAdmissionSeam` per act.
- Neighbours unmodified: Risk Authority 0.8.0, Phase 5A 0.2.0, 5B-4 0.1.0.
