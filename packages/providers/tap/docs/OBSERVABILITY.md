# Observability

`TapInvocationLog` collects `TapInvocationRecord`s. Each record captures: provider
id/version, mapping version, engine mode, compatibility, TAP trace id, normalized
outcome, evidence **count**, evidence **coverage ratio**, result fingerprint, and —
on failure — the error class and framework failure class.

**No unrestricted evidence content and no secrets are ever recorded** — only counts
and coverage ratios. Records are captured separately from platform milestone/audit
events. Enforced by `tests/mapping/test_evidence_boundary.py` and
`tests/test_registry_health_observability.py`.
