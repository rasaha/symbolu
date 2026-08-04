# Compatibility and Migration

## New capability — no legacy routing API to preserve

Unlike Cloud Scaling (`cloud_controller`) or Model Selection (`execution_gate`), there was **no
pre-existing importable routing/steering package** in the repository (see
`docs/audits/llm_steering/CANONICAL_SOURCE_AUDIT.md`). The routing logic existed only as research
engines with dict-based I/O and internal-only callers. There is therefore **no legacy import surface to
shim** for this controller, and none is created — creating an empty shim with no real consumer would be
noise.

## If a compatibility surface is ever needed

Any future legacy namespace for routing must be a **logic-free re-export** of
`ugence_llm_steering_controller` with object identity preserved (`legacy_symbol is canonical_symbol`),
plus a `DeprecationWarning` and migration docs — **never** a second implementation. The single-source
guard (`scripts/audit_single_source.py`) will reject a second copy of the canonical controller anywhere
outside the package.

## Migrating research/experiment code onto the canonical contracts (future)

The research route engines (`model_selection_experiment`, `model_selection_pilot`,
`model_selection_reconciliation`) remain in place, unchanged, classified `RESEARCH_ONLY`. They are
distinct algorithms with different I/O; converging them onto the canonical `SteeringRequest` /
`RoutingRecommendation` contracts is a **future, evidence-backed** phase, not this structural one. A
research harness may already *drive* the canonical controller (supply candidates, policy, fixtures) and
*score* its output without carrying a second routing engine.

## Interop with `ugence-model-selection`

The two packages are complementary and independently installable. A governed runtime that wants both can
install both; neither imports the other. No migration is required in either direction.

## Versioning

`ugence-llm-steering-controller` starts at `0.1.0`. Contract, policy, and registry schema versions are
surfaced (`SCHEMA_VERSION`, `POLICY_VERSION`, `registry_schema_version`) and stamped into results so a
consumer can detect a contract change. Additive contract changes bump the minor version; a breaking
contract change bumps schema/policy versions and is called out in the changelog.
