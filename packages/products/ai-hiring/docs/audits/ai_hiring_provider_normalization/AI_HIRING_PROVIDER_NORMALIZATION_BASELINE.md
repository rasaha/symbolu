# AI Hiring — Canonical TAP / ActionGate Dependency Normalization — Baseline & Result

Machine-readable companion:
[`ai_hiring_provider_normalization_baseline.json`](./ai_hiring_provider_normalization_baseline.json).
Behavioral captures:
[`artifacts/`](./artifacts/). Reference inventory:
[`LEGACY_PROVIDER_REFERENCE_INVENTORY.md`](./LEGACY_PROVIDER_REFERENCE_INVENTORY.md).

## Live-state audit (recorded before any code change)

- **Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
- **Starting commit:** `0daaf2bb7d43e1e07be135279fa192b237e0636e`
- **Working branch:** `claude/ai-hiring-canonical-providers-5pbhlk` (started at the default HEAD; working tree clean)
- **Prerequisite PR #1299** (ActionGate packaging): `closed`, **merged**, merge commit
  `0daaf2bb7d43e1e07be135279fa192b237e0636e`, final head `ee9d7ecf9bae316ec919184fa09d677bb6dd3de9`.
- **Existing AI Hiring dependency-normalization PR:** none found.
- **Canonical distributions verified live:** `ugence-tap-provider` 0.1.0,
  `ugence-actiongate-provider` 0.1.0, `ugence-governance-provider-framework` 0.1.0,
  `ugence-governance-contracts` 0.1.0, `ugence-decision-authority` 1.0.0,
  `ugence-ai-hiring` 0.1.0. Canonical classes: `ugence_tap_provider.provider.TAPProvider`
  (AssertionGovernanceProvider), `ugence_actiongate_provider.provider.ActionGateProvider`
  (ActionGovernanceProvider).

### Baseline measurements

| Item | Value |
|---|---|
| AI Hiring package suite | 774 passed, 6 skipped |
| Monorepo `ai_hiring` suite | 778 passed |
| Pre-existing failures | none |
| Baseline wheel | `ugence_ai_hiring-0.1.0-py3-none-any.whl` (`ce4c7c16…`) |
| Baseline sdist | `ugence_ai_hiring-0.1.0.tar.gz` (`331c431f…`) |
| Baseline extras | `tap → dgm-tap-provider`, `actiongate → dgm-actiongate-provider` |
| Public top-level API hash | `0c6d7ed6…` (unchanged after) |
| Baseline behavioral hash (product / adapter) | `d6984ee7…` / `ad6ba33b…` |
| Platform-freeze manifest digest | `05fdb1ca…` |
| Platform-freeze substantive digest | `d993093570bb8ee1…` (PASS) |
| AI Hiring a frozen component? | No (freeze covers the providers/kernel, not the AI Hiring wheel) |

## Change surface (allowlist)

Production changes are limited to:

- `packages/products/ai-hiring/pyproject.toml` (extras only)
- `packages/products/ai-hiring/src/ugence_ai_hiring/integrations/**` (adapters + facades + exception alias)
- `packages/products/ai-hiring/src/ugence_ai_hiring/version.py` (distribution version + metadata probes)
- `packages/products/ai-hiring/scripts/**` (verifier + capture)
- `packages/products/ai-hiring/docs/**`, `README.md`, `CHANGELOG.md`
- `packages/products/ai-hiring/tests/**`, `packages/products/ai-hiring/artifacts/public_api_baseline.json`
- `.github/workflows/ai-hiring-package-ci.yml`
- `docs/audits/ai_hiring_provider_normalization/**`

**No AI Hiring domain behavior changed** under `evidence`, `ontology`, `rubrics`,
`assessments`, `recommendations`, `decisions`, `actions`, `repositories`, `audit`,
or product runtime. Enforcement: the AST dependency-boundary tests
(`tests/packaging/test_dependency_boundaries.py`) and the H2–H6 boundary tests
prove the domain/core modules import no concrete provider namespace, and the
behavioral-equivalence capture proves product semantics are byte-identical.

## Result

| Item | Value |
|---|---|
| Final distribution version | **0.1.1** (0.1.0 → 0.1.1; packaging patch) |
| Product version | **0.6.0** (unchanged) |
| `production_certified` | **False** (unchanged) |
| Final `tap` extra | `ugence-tap-provider>=0.1.0` |
| Final `actiongate` extra | `ugence-actiongate-provider>=0.1.0` |
| `dgm-*` requirements in final wheel METADATA | **0** |
| Final wheel | `ugence_ai_hiring-0.1.1-py3-none-any.whl` (`8757d179…`) — BIT_FOR_BIT reproducible |
| Final sdist | `ugence_ai_hiring-0.1.1.tar.gz` (`c4eea23f…`) — CONTENT reproducible |
| Package suite (providers on path) | 793 passed, 7 skipped |
| Package suite (core-only path) | 788 passed, 12 skipped |
| Monorepo `ai_hiring` suite | 778 passed |
| Distribution verifier | **CANONICAL_PROVIDER_DEPENDENCIES_VERIFIED** (core-only, TAP-only, ActionGate-only, combined, legacy-deployment) |
| Platform-freeze substantive digest | `d993093570bb8ee1…` — **unchanged** (no freeze fields changed) |

### Behavioral equivalence

`product_semantics_before == after_canonical == after_legacy_paths` and
`adapter_semantics_before == after_canonical == after_legacy_paths`
(product `d6984ee7…`, adapter `ad6ba33b…`). The only differences across the
snapshots are the permitted ones — distribution version, dependency distribution
name, provider import namespace, and adapter module label — all recorded under
`metadata` and excluded from the semantic hashes.

- **Verdict:** EQUIVALENT
- **Classification:** DEPENDENCY_METADATA_ONLY · IMPORT_NAMESPACE_ONLY · ADDITIVE_COMPATIBILITY_SURFACE
- **Semantic regression:** none

## Platform-freeze discipline

This phase touches no frozen tree (`decision_governance`, `governance_providers`,
`actiongate_provider`, `tap_provider`) and no frozen public API. The freeze
substantive digest is byte-identical to the baseline
(`d993093570bb8ee1…`); **no freeze fields changed.** AI Hiring is not itself a
frozen component in `PLATFORM_FREEZE_V1.json`.

**Rollback:** revert this PR's commits (or `git revert` the merge). Because the
change is dependency metadata + isolated adapters + tests/docs, reverting restores
the 0.1.0 extras (`dgm-*`) and the pre-migration adapter modules with no data or
behavioral migration to undo; the platform freeze is unaffected either way.
