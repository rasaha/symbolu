# Versioning

Five version concepts are tracked separately:

| Concept | Value | Notes |
|---|---|---|
| Provider implementation | `0.2.0` | bumped by the vNext semantics change |
| Canonical distribution (`ugence-actiongate-provider`) | `0.2.0` | tracks the implementation |
| Legacy compatibility distribution (`dgm-actiongate-provider`) | `0.2.0` | compat shell, bumped in lockstep |
| Contract (`ActionGovernanceProvider`) | `1.0.0` | framework contract |
| Mapping | `actiongate-map-2` | reported in observability |

`ugence_actiongate_provider.version_info()` reports all of these plus resolved
dependency versions, compatible kernel majors, `build_commit`, and
`production_certified = False`.

A path migration does **not** bump the implementation version. The public `.api`
surface is byte-identical to the pre-migration surface; the only additive change is
the top-level `version_info()` helper (MINOR-compatible overall; the frozen `.api`
snapshot is unchanged). Change classes follow the platform policy: PATCH / MINOR /
MAJOR.

## The 0.1.0 -> 0.2.0 bump

The vNext step is a MAJOR change under the platform's own compatibility rules —
`authority/lifecycle/dependency-direction/fail-safe changes` — because a live
input that previously yielded `AUTHORIZED` now yields a non-authorizing outcome.

It is a **minor-position** bump, not `1.0.0`, because the distribution is pre-1.0
and `version_info().production_certified` is `False`. Moving to `1.0.0` would
assert a production certification this package explicitly denies. On a 0.x line
the minor position is where a breaking change goes.

Why bump at all, when the platform's classifier says the change is additive:
`platform_freeze.compat.classify` compares public API *shape*, and every shape
change in this step was an addition, so it reported the change as
MINOR/ADDITIVE. With the classifier structurally unable to see a fail-safe
change, the version string is the only machine-readable signal a consumer has.
Leaving it at `0.1.0` would have made the change invisible to every automated
downstream check.

Consumers, and what the bump costs each:

| Consumer | Declaration | Effect |
|---|---|---|
| `packages/products/ai-hiring` (`actiongate` extra) | `ugence-actiongate-provider>=0.1.0` | resolves to 0.2.0 with no edit — **a floor does not stop a semantics change**, which is the point of also recording this in the changelog |
| `packages/integration/risk-authority-runtime` | `ugence-actiongate-provider>=0.1.0` | same |
| `packaging/dgm-actiongate-provider` | `ugence-actiongate-provider[decision-authority]==0.2.0` | bumped, and the shell's own version with it |
| four `dgm-*` validation/benchmark distributions | `dgm-actiongate-provider==0.2.0` | bumped; an exact pin left at `0.1.0` would have become unresolvable |
| `platform_freeze.version.COMPONENT_VERSIONS` | `dgm-actiongate-provider: 0.2.0` | bumped, and `platform/PLATFORM_FREEZE_V1.json` regenerated (`components`, `manifest_digest`) |

The two `>=0.1.0` floors are deliberately left alone. Raising them to `>=0.2.0`
would be a compatibility claim about ai-hiring and risk-authority-runtime that
this change did not verify.
