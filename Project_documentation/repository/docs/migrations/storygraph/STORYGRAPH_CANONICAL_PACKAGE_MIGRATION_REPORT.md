# StoryGraph Canonical-Package Migration — Report

**Verdict: `CONTINUE — StoryGraph canonical-package migration passed`.**

This phase reorganizes StoryGraph into one canonical, independently packageable
Ugence capability while preserving all matching, policy, replay, evidence, and
advisory-authority semantics. Legacy imports remain available through explicit
compatibility layers, historical evaluation evidence remains reconstructable, and
no other Ugence capability or shared governance contract is redesigned. Passing
this phase proves the repository migration method for subsequent
capability-by-capability restructuring.

---

## Branches & commits

| Item | Value |
|---|---|
| Source branch | `claude/ugence-modularity-audit-uujl0h` |
| Source commit | `c10f21f48e55212f80704dbc2a6c1749777a76e0` |
| Target / implementation branch | `claude/storygraph-canonical-package-migration-m25c2i` |
| Starting commit (== source tree) | `6a49634e614120cd46beda395d993cb4c6590383` (`git diff c10f21f HEAD` empty) |
| Ending commit | see `git log` head of the implementation branch |
| Commit sequence | baseline → relocate → compatibility → verifier → docs+report |

## Files moved

- **Core source:** `cyber_security/composite_threat_detector/composite_threat_detector/*.py`
  (41 modules) + `policypack/` → `packages/capabilities/storygraph/src/ugence_storygraph/`.
- **Evaluation infra (15 .py) + demos (2 .py):** folded in as
  `ugence_storygraph/evaluation/` and `ugence_storygraph/demos/` (were floating
  sibling top-level packages).
- **Replay intake (schema + templates):** → `ugence_storygraph/replay_intake/`
  (now a shippable subpackage).
- **Tests (24 files, 289 tests):** → `packages/capabilities/storygraph/tests/`,
  imports rewritten to `ugence_storygraph`.
- **Documentation (13 .md):** → `packages/capabilities/storygraph/docs/`.

All moves are git-tracked **renames** (history preserved).

## Files retained as compatibility layers

- `cyber_security/composite_threat_detector/composite_threat_detector/__init__.py`
  — logic-free redirect shim (meta-path finder + public re-export).
- `cyber_security/composite_threat_detector/conftest.py` — legacy path bootstrap.
- `Project_documentation/action_gate_cyber/cyber_security/composite_threat_detector/README.md` — "moved" pointer.

## Files classified as non-StoryGraph

None. The entire moved tree is the single canonical StoryGraph capability; no
`RESEARCH`/`DUPLICATE`/`DEPRECATED`/`UNRELATED` artifact was found (see
`FILE_MAP.md`). No other capability was touched.

## Test counts

| | Collected | Passed | Failed | Skipped | Deselected |
|---|---|---|---|---|---|
| **Baseline** (old location) | 289 | 289 | 0 | 0 | 0 |
| **Final** (canonical package) | 311 | 311 | 0 | 0 | 0 |

Final = 289 relocated + **22 new** compatibility/contract tests
(`tests/compatibility/`). **Skipped / infrastructure-dependent tests: 0** — the
suite is deterministic, stdlib-only, needs no network/GPU/DB/credentials/cluster.

## Public API — before & after

- **Before:** 75 symbols on `composite_threat_detector.__all__`.
- **After:** 76 on `ugence_storygraph.__all__` — **0 removed, 1 added** (`api`,
  the curated small public surface). Every one of the 75 baseline symbols is the
  **same object** on both the canonical namespace and the legacy path (identity
  verified). Curated `ugence_storygraph.api` exposes 61 `PUBLIC_STABLE` symbols;
  internal module handles remain on the full namespace but are not promoted.

## Import graph — before & after

Both stdlib-only, zero third-party, zero Ugence-package imports, zero prohibited
cross-capability edges. Details in `IMPORT_GRAPH.md`. Machine-enforced by
`tests/compatibility/test_dependencies.py` and the distribution verifier.

## Distribution name & namespace

- Distribution: **`ugence-storygraph`** · Namespace: **`ugence_storygraph`**
  (verified no conflict with existing `packaging/` distributions).

## Packaging results

| Check | Result |
|---|---|
| Wheel build | ✅ `ugence_storygraph-2.0.0-py3-none-any.whl` (schemas/fixtures/templates ship as package data) |
| Clean-venv install | ✅ `pip install --no-index` succeeds (zero third-party deps) |
| Independent-distribution proof | ✅ `verify_storygraph_distribution.py` passes: imports from site-packages, no monorepo path, no unrelated Ugence package importable, reference eval + policy-pack compile + replay reproduce recorded digests |

## Frozen digest comparisons (baseline → final)

| Anchor | Baseline | Final | |
|---|---|---|---|
| `ACCOUNT_TAKEOVER_TRANSFER@1.0.0` | `…6a77b899…081a8` | identical | ✅ |
| `DIGITAL_EXFILTRATION_STORY@1.0.0` | `…a8bce847…8d9e1` | identical | ✅ |
| Reference graph freeze digest | `…6a77b899…081a8` | identical | ✅ |
| Reference bundle digest | `…f6323c92…96a1e` | identical | ✅ |
| Pre-registration digest | `…1f026c7a…422d4` | identical | ✅ |
| PolicyPack schema bytes | `…24bc416e…70779` | identical | ✅ |
| All version identifiers | (see BASELINE §4) | identical | ✅ |

## Replay digest comparison

Deterministic replay report digest
`sha-256:0dcf2bc4730bf12a89e5e5e6b54b8a9442b59b105dc068659d8035033977923b` —
**identical** baseline → final, and reproduced again inside the isolated wheel
install. Pinned by `tests/compatibility/test_digest_stability.py`.

## Compatibility-test results

`tests/compatibility/` — **22/22 pass**: legacy⇄canonical object identity
(top-level, submodule, deep, lazy), no symbol disappeared, dataclass
serialization identical, digest stability, advisory-authority boundary,
non-mutation, dependency compliance.

## Authority-boundary result

StoryGraph remains **advisory**. Signal vocabulary is exactly
`{OBSERVE, ESCALATE, UNAVAILABLE}`; advisory evidence is classed `ADVISORY` with
an `OBSERVE`/`ESCALATE` effect ceiling; no binding verb
(`ALLOW`/`DENY`/`AUTHORIZE`/`BLOCK`/`EXECUTE`/`CLEAR`/`PERMIT`) exists on the
public API or is emitted. It cannot authorize, clear, decide, or execute.

## Freeze-manifest changes

**None owed at the platform level** — StoryGraph is **not** part of
`platform/PLATFORM_FREEZE_V1.json` (verified: zero references). Its **own**
internal freeze (`ugence_storygraph/evaluation/freeze.py` + digests) is preserved
and verified unchanged. Historical evaluation records
(`evaluation/prior_runs.py`, evidence-ledger docs) are carried forward verbatim;
the `APPROVED_EVIDENCE_PATHS` governance globs were relocated (source + test
together) to the new physical path — these are path globs, not digest inputs.

## Known limitations

- Synthetic-only validation; one implemented harmful domain (account-takeover)
  plus a digital-exfiltration story; known-pattern-only scope; no malicious-intent
  inference; no direct enforcement authority (all by design — see README).
- The legacy compatibility shim relies on a source-checkout `sys.path` bootstrap
  when `ugence_storygraph` is not installed; documented and confined to the shim.
- Governance-contract enrichment (tenant/authority/correlation) intentionally
  **not** done here — deferred to the governance-contracts migration.

## Rollback procedure

1. `git revert` the migration commits in reverse (report → verifier →
   compatibility → relocate → baseline), **or** check out `6a49634` (tree
   identical to source `c10f21f`).
2. No data/evidence loss: every move is a git rename; historical evaluation
   records and evidence ledgers are preserved verbatim; all digests reproduce
   from either layout. The compatibility shim is independently removable at v3.0.0.

## Acceptance gates

| Gate | Status | Evidence |
|---|---|---|
| S1 exact baseline | ✅ | `BASELINE.md`, `BASELINE_manifest.json`, dedup test manifest |
| S2 one canonical source | ✅ | single tree in `src/ugence_storygraph/`; legacy path is a logic-free redirect, not a copy |
| S3 zero semantic change | ✅ | all digests/versions/API identical (this report) |
| S4 public API compatibility | ✅ | canonical + legacy imports resolve to same objects; 22 compat tests |
| S5 independent packaging | ✅ | clean-venv `--no-index` wheel install + verifier |
| S6 test co-location | ✅ | tests owned by the package; legacy invocation still supported |
| S7 dependency compliance | ✅ | stdlib+self only; AST scan + verifier; import-graph doc |
| S8 authority preservation | ✅ | advisory-only; authority-boundary tests |
| S9 freeze preservation | ✅ | not in platform freeze; internal freeze + evidence preserved |
| S10 rollback safety | ✅ | git renames; revert/checkout procedure above |

---

## Final verdict

**`CONTINUE — StoryGraph canonical-package migration passed`.**

This phase reorganizes StoryGraph into one canonical, independently packageable
Ugence capability while preserving all matching, policy, replay, evidence, and
advisory-authority semantics. Legacy imports remain available through explicit
compatibility layers, historical evaluation evidence remains reconstructable, and
no other Ugence capability or shared governance contract is redesigned. Passing
this phase proves the repository migration method for subsequent
capability-by-capability restructuring.
