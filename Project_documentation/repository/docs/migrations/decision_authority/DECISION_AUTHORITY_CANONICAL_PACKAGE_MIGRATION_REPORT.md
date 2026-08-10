# Decision Authority — Canonical-Package Migration Report

## Branches & commits

- **Source/target branch:** `claude/decision-authority-canonical-package-migration`
- **Starting commit:** `8946df9c` (integrated default: StoryGraph + terminology + Governance Contracts all merged)
- **Ending commit:** this branch tip (see git log)

## What moved / what was excluded

- **Moved (pure `git mv`, history preserved):** the bounded domain-neutral kernel
  `decision_governance/**` → `packages/capabilities/decision-authority/src/ugence_decision_authority/**`
  (95 `.py`, 7616 LOC). All internal imports are relative → **no import edits** for the move.
- **Excluded (out of scope):** `domains/{hiring,procurement}`, `ai_hiring`, `applications`,
  console, providers (`governance_providers`, `tap_provider`, `actiongate_provider`), ACP,
  StoryGraph, Agent Runtime, Model Selection, Hybrid LLM, LLM Steering, the AI Control Plane /
  optional orchestrator, product compositions, and research. See `CLASSIFICATION.md`.

## Canonical namespace & distribution

- **Namespace:** `ugence_decision_authority` · **Distribution:** `ugence-decision-authority`
- **Legacy compatibility:** `decision_governance` namespace (logic-free shim, identity-preserving)
  and the `decision-governance` distribution (compatibility shell depending on the canonical wheel).

## Public API — before vs after

- Top-level `__all__`: **16 symbols**, identical objects via both namespaces.
- `.api` surface: identical; the freeze `public_api_manifests.decision_governance.api` hash and
  the api-snapshot file are **byte-identical** (`1b89386992bb…`). No symbol added/removed/renamed;
  no internal helper promoted. See `PUBLIC_API_INVENTORY.md`.

## Test counts

- **Baseline:** 29 deduplicated kernel tests (`test_manifest.txt`).
- **Canonical package:** **79 passed** (29 frozen surface/vocabulary/serialization guards,
  rewritten layout/packaging guards, new legacy-compatibility identity tests, prohibited-import
  and leafward-dependency tests).
- **Consumer suites:** ai_hiring **778**, domains+applications **32**, governance_providers **42**,
  tap_provider+actiongate_provider **68**, agent_runtime_migration — all green
  (combined consumer sweep **995 passed**).
- **Regression:** governance-contracts **45**, StoryGraph **316** — unchanged.

## Serialization & digest comparisons

Equivalence fingerprint (`scripts/da_migration_capture.py`), before vs after — **identical**:

| Fingerprint | Before | After |
|---|---|---|
| version | `1.0.0` | `1.0.0` |
| public API sha256 | `82685c11…` | `82685c11…` |
| pydantic models digest (29) | `ecf2af54…` | `ecf2af54…` |
| enums digest (30) | `f7034fa9…` | `f7034fa9…` |
| per-model JSON-schema diffs | — | **0 / 29** |

## API-snapshot comparison

All four `platform/api-snapshots/*.json` **byte-identical** after re-baseline (verified via diff).

## Import graph before / after

See `IMPORT_GRAPH_BEFORE.md` / `IMPORT_GRAPH_AFTER.md`. Kernel imports only pydantic + stdlib
(no Ugence package; does not import `ugence_governance_contracts`). Consumers unchanged; the
capability remains a leaf; no cycles.

## Packaging results

- **Wheel build:** OK (version read statically from `version.py`).
- **Wheel contents:** only `ugence_decision_authority/` + dist-info; no tests, no foreign package.
- **Clean install / isolated distribution:** `verify_decision_authority_distribution.py` → **VERIFIED ✔**
  (installs in a fresh venv with pydantic from index; imports from site-packages; public API +
  representative record schema + vocabulary + `canonical_hash`; no sibling Ugence package importable).

## Freeze changes

Structural re-baseline via `platform_freeze.write_manifest()`. Exactly **two** fields changed:

| Field | Before | After |
|---|---|---|
| `core_tree_hashes.decision_governance` | `f38a6159…` | `3e98d8db…` (shim tree) |
| `manifest_digest` | `f318dfd2…` | `6fb6d6c8…` |

Byte-identical: `public_api_manifests.decision_governance.api` (`1b893869…`), all api-snapshots,
`components` (`decision-governance: 1.0.0`), other core-tree hashes, conformance hashes,
dependency rules. `python -m platform_freeze.verify` → **PASS**. API compatibility classification:
**structural / PATCH** (no substantive API change).

## Known pre-existing failures (unrelated — not touched)

`platform_freeze/tests`: 2 pre-existing failures (`test_classify_change_reports_evidence`,
`test_hiring_baseline_discovery`), documented in the Governance Contracts migration; **not fixed
here** (§19).

## Necessary relocation adjustment (documented)

The kernel conformance kit's "is this a kernel type" check hard-coded the module prefix
`"decision_governance."`. It now accepts the canonical prefix `"ugence_decision_authority."`
**and** the legacy prefix — an identity-path update required by the rename, with zero behavior
change for kernel records. Three consumer *tests* (ai_hiring, procurement) that asserted the old
`__module__` string were similarly updated to accept the canonical prefix. No consumer business
logic, and no error code/message, enum value, serialization, hash, or authority rule, was changed.

## Known limitations

- The `decision_governance` name overload persists in code via the compatibility shim until its
  2.0.0 removal (deferred).
- The freeze `core_trees` still lists `decision_governance` (now the shim); the canonical
  implementation tree is guarded by the byte-identical API manifest hash + the distribution
  verifier + tests (same approach as the Governance Contracts migration), not a new core-tree
  entry.

## Rollback procedure

`git revert`/reset this branch to `8946df9c`, or `git mv` the canonical tree back and delete the
shim; the freeze re-baseline is reproducible via `platform_freeze.write_manifest()`. History is
preserved (renames), so no API, evidence, or package history is lost. The compatibility shim is
independently removable at 2.0.0.

## Remaining future work (deferred)

- Migrate consumers' imports from `decision_governance` to `ugence_decision_authority` and retire
  the shim (2.0.0).
- Governance Provider Framework migration (roadmap step 6); Model Selection classification (step 7).
- The umbrella *Ugence Decision Governance*, AI Control Plane, optional orchestrator, Governance
  Services Layer, and the *Decide* product remain out of scope (not code modules of this capability).

---

## Verdict

**CONTINUE — Decision Authority canonical-package migration passed.**

This phase reorganizes the bounded Decision Authority kernel into one canonical, independently
packageable Ugence capability while preserving the frozen decision_governance public API,
binding-decision authority, tenant isolation, CER and decision semantics, segregation of duties,
overrides, audit behavior, serialization, digests, and consumer compatibility. The legacy
decision_governance namespace remains available through explicit compatibility layers. Ugence
Decision Governance, the AI Control Plane, optional orchestrator, Governance Services Layer,
Decide product, domain applications, and other capabilities remain outside this migration.
