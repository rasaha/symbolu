# Governance Provider Framework — Canonical-Package Migration Report

Implementation phase completing restructuring-roadmap step 6. Relocates the
capability-neutral Governance Provider Framework into one canonical, independently
packageable Ugence package, with zero authority expansion, zero semantic change,
complete backward compatibility, and independent-distribution proof.

## Branches & commits

| Item | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default HEAD (start) | `ed7387f4` — Merge PR #1266 |
| Migration (feature) branch | `claude/gpf-canonical-package-migration-y3qoew` (harness-designated; based on `ed7387f4`) |
| Starting commit | `ed7387f4576bf111c7f5544958dfb30bbe524906` |
| Environment | Linux, Python 3.11.15; installed dependency gaps at start: `pytest`, `pydantic`, `numpy`, `build` (pip-installed; no repo file changed to do so) |

> **Branch-name note.** The prompt proposed
> `claude/governance-provider-framework-canonical-package-migration`; the harness
> mandates `claude/gpf-canonical-package-migration-y3qoew` and forbids pushing
> elsewhere. All work is on the harness branch, based on the latest integrated
> default tip. No PR opened (none requested).

Commit sequence (small, reviewable, not squashed):
1. record canonical-package migration baseline
2. add canonical framework package skeleton
3. relocate framework core and add legacy compatibility shim
4. relocate and strengthen framework tests
5. convert legacy distribution to compatibility shell
6. add independent distribution verification
7. re-baseline structural freeze metadata
8. document canonical migration evidence (this report)

## Canonical & legacy identifiers

| Role | Value |
|---|---|
| Canonical path | `packages/governance-provider-framework/` |
| Canonical namespace | `ugence_governance_provider_framework` |
| Canonical distribution | `ugence-governance-provider-framework` |
| Legacy namespace (compat shim) | `governance_providers` |
| Legacy distribution (compat shell) | `dgm-provider-framework` |

## Files moved / excluded / added

- **Moved (history-preserving `git mv`):** 29 non-test modules →
  `src/ugence_governance_provider_framework/`; 9 test files → the canonical package
  `tests/` tree. Full table in `FILE_MAP.md`. **No source import changed** — all
  internal imports are package-relative; only the three `adapters/*` bind
  `decision_governance.api` (unchanged). Test imports were rewritten to the
  canonical namespace (relocation-driven only).
- **Excluded from the canonical wheel:** tests, applications, domains, research,
  migration reports, concrete providers, Governance Contracts (imported, not
  copied). Verified: the built wheel contains only
  `ugence_governance_provider_framework/` + dist-info.
- **Added:** package `pyproject.toml`/`README`/`CHANGELOG`/`MIGRATION`/`LICENSE`/
  `.gitignore`/`conftest.py`; `verify_governance_provider_framework_distribution.py`;
  `tests/compatibility/test_legacy_namespace.py`; `tests/kernel_lifecycle.py`;
  the `governance_providers` legacy shim; `scripts/gpf_equivalence_capture.py`;
  this migration evidence set.

## Adapter classification (the principal boundary issue)

All three modules referencing `decision_governance.api` are
**GENERIC_FRAMEWORK_ADAPTER** — capability-neutral kernel ports with no
`tap`/`actiongate` coupling (grep-verified). Full table in
`ADAPTER_CLASSIFICATION.md`. Resolution: kept in the framework (preferred outcome
#1), physically isolated in `adapters/`, with `decision-governance` declared an
**optional** distribution extra so the core never acquires a mandatory dependency
on a bounded capability. Adapter behaviour is unchanged when the extra is
installed.

### Optional-dependency boundary correction (PR-validation phase)

To make Decision Authority genuinely optional at the import boundary, the three
adapters now load the kernel **lazily**: module-level kernel imports and the frozen
`_OUTCOME_MAP` moved into a cached `_kernel()` loader; the `__init__` id/clock
defaults became lazy delegating wrappers; a centralized
`adapters/_kernel.py::require_decision_authority()` raises a precise
`ModuleNotFoundError` naming `ugence-governance-provider-framework[adapters]` (only
for the specific absence of Decision Authority — unrelated import errors propagate).
As a result the canonical public API `ugence_governance_provider_framework.api` —
including the adapter symbols — imports **without** Decision Authority; only
*invoking* an adapter requires the extra. This is an import-boundary correction
only: public class names, method signatures, fields, enums, errors, serialization,
and adapter behaviour with the extra installed are unchanged; the frozen
`governance_providers.api` snapshot stays byte-identical (`98dd0264…`) and the
behavioural fingerprint is unchanged (`a8e3e7e9…`). Proven by
`tests/boundaries/test_optional_adapter_dependency.py` and the distribution
verifier's core-only scenario.

## Public API — before and after

- Surface: `governance_providers.api` — **48** exported symbols (the audit's "47"
  undercounted by one; see `PUBLIC_API_INVENTORY.md`). 31 re-exported from the
  contracts leaf, 12 framework-owned, 5 kernel-bound adapters.
- **API snapshot byte-identical:** `governance_providers.api` snapshot hash
  `98dd02649e5fbb37879ef05e1b06afce1abd0cc10b5692b81974437d59f7a59b` before and
  after (the freeze tooling snapshots the legacy name via the shim). The canonical
  `ugence_governance_provider_framework.api` symbol table is byte-for-byte
  identical (only the recorded `module` name field differs, which the frozen
  snapshot does not use for that surface).
- `api_compatibility` classification: **PATCH** (0 diffs).
- Legacy and canonical imports resolve to the **same objects** (identity), for the
  aggregated API and every deep submodule.

## Exact test counts — baseline vs final

| Suite | Baseline | Final | Note |
|---|---|---|---|
| Framework (behavioural) | 42 | 42 | preserved verbatim; relocated into unit/conformance/integration |
| Framework package total | — | 84 | +42 new: strengthened boundaries, packaging, legacy-namespace identity, and the optional-adapter dependency boundary |
| tap_provider | 38 | 38 | via shim |
| actiongate_provider | 30 | 30 | via shim |
| baselines (assertion+action) | 10 | 10 | via shim |
| governance-contracts | 45 | 45 | incl. legacy deep-import compat matrix |
| decision-authority | 79 | 79 | unchanged |
| storygraph | 316 | 316 | unchanged |
| ai_hiring | 778 | 778 | deep-imports `.contracts`/`.reference` via shim |
| enterprise_validation_pilot | 164 | 164 | via shim |
| provider_heterogeneity_validation | 51 | 51 | uses `.version` via shim |
| comparative_governance_benchmark | 56 | 56 | via shim |
| platform_freeze/tests | 19 pass / **2 pre-existing fail** | 19 pass / **2 pre-existing fail** | no regression (see below) |

**Pre-existing failures (unchanged, not caused by this migration, not fixed per
§24):** `platform_freeze/tests/test_freeze.py::test_classify_change_reports_evidence`
and `::test_hiring_baseline_discovery` — stale tooling unit assumptions from earlier
phases. The freeze **verifier** passes.

## Equivalence evidence

| Dimension | Result |
|---|---|
| Registry / duplicate-registration / lifecycle | byte-identical (behavioural capture) |
| Deterministic resolution (all 3 kinds) | byte-identical |
| Metadata / serialization / enums | byte-identical (API snapshot) |
| Error types & messages / MRO | byte-identical |
| Fingerprints & hashes | byte-identical (`fingerprint({})` etc.) |
| Reference-provider descriptors | byte-identical |
| Conformance behaviour | tests green, unchanged |
| Deep-import resolution & object identity | preserved (compat suite) |
| Version predicates | byte-identical |

Behavioural equivalence capture (`scripts/gpf_equivalence_capture.py`, through the
legacy surface) — BEFORE `a8e3e7e9…` == AFTER `a8e3e7e9…` (byte-identical). Dumps
saved as `equivalence_before.json` / `equivalence_after.json`.

## Import graph before / after

See `IMPORT_GRAPH_BEFORE.md` and `IMPORT_GRAPH_AFTER.md`. Direction unchanged and
acyclic; zero upward imports; the pure core imports no bounded capability; only
`adapters/` bind the kernel facade (optional). All 66 consumers resolve via the
identity-preserving `governance_providers` shim with no edits.

## Packaging & independent-distribution proof

`verify_governance_provider_framework_distribution.py` builds the local wheels and
runs six isolated venv scenarios (no monorepo path). All pass:

| Scenario | Result |
|---|---|
| Canonical wheel builds; bundles only its namespace, no tests, no providers | ✔ |
| **1/3.** canonical wheel only — core installs (contracts only); `.api` **and** `.adapters` import; registry/resolution/conformance run; invoking a kernel-bound adapter raises the precise `[adapters]` error; **Decision Authority NOT pulled/installed** | ✔ |
| **4.** canonical wheel `[adapters]` — full 48-symbol public API + adapters + resolve | ✔ |
| **2.** legacy `dgm-provider-framework` wheel — `governance_providers` resolves to the SAME objects as canonical | ✔ |
| **5.** `dgm-tap-provider` runs against the installed canonical framework | ✔ |
| **6.** `dgm-actiongate-provider` runs against the installed canonical framework | ✔ |

Canonical wheel declares Governance Contracts explicitly; declares Decision
Authority only as the optional `adapters` extra; bundles no TAP/ActionGate.

## Freeze changes (reviewed, structural / PATCH)

Exactly two manifest fields changed (diff is two lines):

| Field | Before | After |
|---|---|---|
| `core_tree_hashes[governance_providers]` | `ab12c026…` | `9ec688e6…` (now the logic-free shim tree) |
| `manifest_digest` | `6fb6d6c8…` | `bd346cb2…` |

`governance_providers.api` snapshot file byte-identical (`d4266914…`); all other
fields, components, conformance hashes, dependency rules, and invariants unchanged.
`python -m platform_freeze.verify`: **PASS**. Substantive digest moved
`477407…` → `d4ad77e1…` (reflects the two structural fields only).

## Acceptance gates

| Gate | Verdict |
|---|---|
| GPF1 exact baseline | ✅ recorded (`BASELINE.md`, manifests, inventories) |
| GPF2 framework boundary preserved | ✅ only capability-neutral mechanics canonicalized |
| GPF3 adapter boundary resolved | ✅ Decision Authority optional; no mandatory core dep |
| GPF4 one canonical source | ✅ single physical tree; legacy is a shim |
| GPF5 zero semantic change | ✅ behavioural capture + API snapshot byte-identical |
| GPF6 public API compatibility | ✅ canonical + legacy imports work; identity preserved |
| GPF7 independent packaging | ✅ six isolated-venv scenarios pass |
| GPF8 concrete-provider integrity | ✅ TAP 38 / ActionGate 30 green; installed-wheel proofs pass |
| GPF9 dependency direction | ✅ core deps: contracts + stdlib only; kernel optional |
| GPF10 no authority expansion | ✅ authority-neutral; no router/adjudicator/orchestrator added |
| GPF11 freeze & API preservation | ✅ 2 justified structural fields; API PATCH |
| GPF12 consumer integrity | ✅ all affected suites green, no edits |
| GPF13 historical evidence preserved | ✅ audit + before snapshots + this evidence set intact |
| GPF14 rollback safety | ✅ see procedure below |

## Rollback procedure

The migration is `git`-reversible with no loss of API, history, or compatibility:

1. `git revert` (or reset) commits 3–7 in reverse order — or revert the whole range
   `db8875c0..HEAD` on this branch. Because the relocation is history-preserving
   `git mv`, reverting restores `governance_providers/` as the canonical tree.
2. The freeze re-baseline commit is self-contained (two hash fields); reverting it
   restores `ab12c026…` / `6fb6d6c8…`.
3. No consumer was edited, so nothing else needs unwinding.
4. Re-run `python -m platform_freeze.verify` (expect PASS on the pre-migration
   manifest) and the framework suite to confirm restoration.

## Known limitations / deferred (out of scope this phase)

- **Deferred consumer namespace migration.** All 66 consumers stay on the
  `governance_providers` name via the shim (zero edits), per the Governance
  Contracts precedent. Migrating consumers to `ugence_governance_provider_framework`
  is a later, separate change.
- **Deferred adapter/SDK-runtime split.** `adapters/` is physically isolated, the
  kernel dep is optional, and the adapters load Decision Authority lazily so the
  public API imports without it. A later `sdk`(pure) + `runtime`(kernel-bound)
  **two-distribution** split is therefore possible with no second migration — the
  packaging split itself is not performed now.
- **Deferred contract refinements.** The documented (do-not-act) gaps — neutral
  observability-record base, shared conformance-report base, GC ownership of
  `CONTRACT_VERSION` — remain future, additive, versioned work.
- **`ugence-governance-contracts` freeze folding** — folding the contracts leaf
  into the freeze manifest remains a separate reviewed decision.
- **Two pre-existing `platform_freeze/tests` failures** — stale tooling unit tests,
  unrelated, intentionally not fixed.

## Final summary

This phase reorganizes the capability-neutral Governance Provider Framework into one
canonical, independently packageable Ugence framework while preserving the frozen
`governance_providers` public API, registry behavior, provider resolution, lifecycle,
metadata, configuration, observability, fingerprints, conformance behavior, deep
imports, consumer compatibility, and authority neutrality. The legacy
`governance_providers` namespace and `dgm-provider-framework` distribution remain as
compatibility surfaces. Governance Contracts, Decision Authority, TAP, ActionGate,
ACP, StoryGraph, applications, domains, platform services, products, and concrete
provider authority remain outside this migration.

## Verdict

**CONTINUE — Governance Provider Framework canonical-package migration passed**
