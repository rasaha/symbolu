# Packaging & Compatibility Map — Governance Provider Framework

Audit-only. **No wheel is built, no distribution created, no name selected as
final.** Recommendations are for a later phase.

## 1. Current distribution (already exists)

| Property | Value |
|---|---|
| Distribution name | `dgm-provider-framework` |
| Visibility | **PRIVATE** — "Not published publicly" (`docs/DGM_PROVIDER_FRAMEWORK.md` §8) |
| Import package | `governance_providers` |
| Packaging dir | `packaging/dgm-provider-framework/` |
| Source layout | **symlink** `governance_providers -> ../../governance_providers` (one canonical source tree, packaged directly — no copy) |
| Version | `0.1.0`, dynamic from `governance_providers.version.__version__` |
| Runtime deps | `decision-governance==1.0.0`, `ugence-governance-contracts>=0.1.0` |
| Test extra | `pytest>=7.0` |
| Included packages | `governance_providers*` |
| Excluded | `governance_providers.tests`, `governance_providers.tests.*` |
| Build backend | `setuptools.build_meta` (`setuptools>=61.0`), `requires-python>=3.10` |

## 2. Independent-build assessment

| Question | Answer | Evidence |
|---|---|---|
| Does it build independently? | **Yes** — it is already a standalone distribution with its own `pyproject.toml`, versioned, dependency-pinned | `packaging/dgm-provider-framework/pyproject.toml` |
| Does it contain unrelated packages? | **No** — includes only `governance_providers*` | `[tool.setuptools.packages.find]` |
| Does it depend on application code? | **No** — deps are the kernel dist + the contracts leaf only | dependency list; import graph shows zero app imports |
| Does it contain business/authority logic? | **No** — mechanism + kernel adapters + reference/conformance only | `ARTIFACT_CLASSIFICATION.md` |
| Are concrete providers mixed into this wheel? | **No** — TAP/ActionGate/baselines are separate distributions | see §3 |
| Installed-wheel vs source-checkout behavior | Equivalent — `governance_providers/__init__.py` bootstraps `ugence_governance_contracts` onto `sys.path` **only** in an uninstalled checkout; no-op when installed | `_ensure_governance_contracts_importable()` |
| Source-checkout bootstrap present? | **Yes** (contracts leaf) | as above; plus root `conftest.py` adds `packages/*/src` |
| Object identity preservation needed? | **Yes** — the legacy-compat suite asserts the framework shim paths resolve to the *same* objects as the contracts leaf | `packages/governance-contracts/tests/compatibility/test_legacy_compat.py` |
| Deep imports externally consumed? | **Yes** — `.contracts`, `.reference`, `.version`, `.conformance` (see consumer map) | must be preserved by shims on migration |
| Future compatibility wheel required? | Not a separate wheel — an **identity-preserving legacy namespace shim** at `governance_providers` (same pattern as `decision_governance`, `composite_threat_detector`) | prior migration reports |

## 3. Sibling provider distributions (already separated — do not merge)

| Dir | Distribution | Symlink target | Deps |
|---|---|---|---|
| `packaging/dgm-tap-provider/` | `dgm-tap-provider` | `tap_provider -> ../../tap_provider` | `decision-governance==1.0.0`, `dgm-provider-framework==0.1.0` |
| `packaging/dgm-actiongate-provider/` | `dgm-actiongate-provider` | `actiongate_provider -> ../../actiongate_provider` | `decision-governance==1.0.0`, `dgm-provider-framework==0.1.0` |
| `packaging/dgm-baseline-assertion-provider/` | `dgm-baseline-assertion-provider` | `baseline_assertion_provider -> …` | same two |
| `packaging/dgm-baseline-action-provider/` | `dgm-baseline-action-provider` | `baseline_action_provider -> …` | same two |
| `packaging/dgm-provider-framework/` | `dgm-provider-framework` | `governance_providers -> …` | `decision-governance==1.0.0`, `ugence-governance-contracts>=0.1.0` |

Each concrete/baseline provider is its own private wheel depending on the
framework wheel — **the framework and its implementations are already
physically decoupled at the distribution layer.** Packaging integrity is asserted
by `platform_freeze` (`_packaging_integrity`) and each provider's `test_packaging.py`.

## 4. Namespace & deep-import consumers to preserve

- Legacy top-level name `governance_providers` — all 66 consumer files.
- Submodule paths: `governance_providers.api`, `.conformance`, `.reference[.assertion|.action]`,
  `.version`, `.contracts[.*]`, `.errors`, `.lifecycle`, `.metadata`.
- The contracts-shim identity guarantee (objects `is`-equal to the GC leaf).

## 5. Recommended future canonical distribution (name NOT finalized here)

Only after the boundary is accepted (it is — see `MIGRATION_READINESS_RECOMMENDATION.md`),
the canonical migration should follow the three prior migrations' pattern:

- Canonical path: **`packages/governance-provider-framework/src/ugence_governance_provider_framework/`**
  (a framework leaf parallel to `packages/governance-contracts/`, **not** under
  `packages/capabilities/` — the framework is infrastructure, not a capability).
- Candidate namespace: `ugence_governance_provider_framework`.
- Candidate distribution name: **`ugence-governance-provider-framework`**
  (aligning with `ugence-governance-contracts`, `ugence-storygraph`,
  `ugence-decision-authority`). The names `ugence-governance-provider-sdk` /
  `-runtime` are only appropriate if a later phase splits the pure core from the
  kernel-bound adapters into two distributions (Model B/D); **that split is not
  proposed for the first migration**.
- Keep `dgm-provider-framework` as the private packaging entry (repoint its
  symlink to the new canonical `src/` tree) or retire it in favor of the ugence
  name — a packaging decision for the migration phase, not the audit.

Do not select a name for aesthetics; the recommended
`ugence-governance-provider-framework` matches the proven family convention and
the framework's single-coherent-package boundary.
