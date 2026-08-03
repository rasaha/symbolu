# Versioning

Five version concepts are tracked separately:

| Concept | Value | Notes |
|---|---|---|
| Provider implementation | `0.1.0` | unchanged by the path migration |
| Canonical distribution (`ugence-actiongate-provider`) | `0.1.0` | new |
| Legacy compatibility distribution (`dgm-actiongate-provider`) | `0.1.0` | compat shell |
| Contract (`ActionGovernanceProvider`) | `1.0.0` | framework contract |
| Mapping | `actiongate-map-1` | reported in observability |

`ugence_actiongate_provider.version_info()` reports all of these plus resolved
dependency versions, compatible kernel majors, `build_commit`, and
`production_certified = False`.

A path migration does **not** bump the implementation version. The public `.api`
surface is byte-identical to the pre-migration surface; the only additive change is
the top-level `version_info()` helper (MINOR-compatible overall; the frozen `.api`
snapshot is unchanged). Change classes follow the platform policy: PATCH / MINOR /
MAJOR.
