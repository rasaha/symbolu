# ADR — Behaviour-tree freeze baseline: import correction

**Status:** ratified (owner ruling `BH-IMPORT`)
**Scope:** `platform/PLATFORM_FREEZE_V1.json` → `behaviour_tree_hashes`, `manifest_digest`;
`platform_freeze/manifest.py`; `platform_freeze/verify.py`
**Decision class:** PATCH — no public API, no signed field, no canonical serialization,
no provider contract. The platform-freeze substantive digest
(`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`) is unchanged before
and after this ADR.

## The load-bearing question

Were the three pinned `behaviour_tree_hashes` ever computed from content this repository
holds — and if not, what may be adopted in their place?

They were not, and the answer is the current tracked content, adopted as a baseline import
rather than re-derived. This ADR records why that is a correction of an import, not a
re-baseline caused by a later code change.

## What the repository shows

| Fact | Evidence |
| --- | --- |
| `freeze_commit` `5ae4f70` is not an object in this repository | `git cat-file -e 5ae4f70^{commit}` → `fatal: Not a valid object name`, across all 443 commits reachable from `HEAD` |
| All three trees and the manifest entered together in one commit | `git log --format=%h -- <tree>` returns exactly `eb5ff947` for each of the three; `--diff-filter=A` on `platform/PLATFORM_FREEZE_V1.json` returns the same commit |
| That commit is `eb5ff947`, merge of PR #1641, 2026-09-06 | `git log -1 --format='%H %ad %s' eb5ff947` |
| No behaviour-tree Python file has ever been modified | `--diff-filter=A` counts 46 / 48 / 34 `.py`; `--diff-filter=M` counts 0 / 0 / 0; tracked `.py` today is 46 / 48 / 34 |
| No parameterisation of the hashing reproduces a pinned value | 12 variants per tree (tracked-`.py` / `rglob`-`.py` / all-tracked × with-and-without `tests/` × list-and-dict entry shape) — zero matches for any of the three |
| The three keys were the sole cause of the `manifest_digest` mismatch | recomputing the manifest with only those three keys replaced reproduces the new digest exactly |
| Nothing ever compared them | `verify_manifest` wrote `behaviour_tree_hashes` into the manifest and checked `components`, `core_tree_hashes`, `conformance_hashes`, `public_api_manifests`, `dependency_rules` and `api_compatibility` — never the behaviour hashes |

`[V]` for every row above.

## What follows from it

The pinned values did not describe the content in this repository, and there is no
parameterisation under which they did. **This ADR does not claim they were ever correct.**
It claims something narrower and provable: they cannot be checked here, and the content
they were computed over cannot be recovered here. Restoration is impossible from this
repository — there is no commit, no tag and no object holding a behaviour tree whose
digest is any of the three.

`5ae4f70` is preserved in this record as **unverifiable foreign provenance**: a commit
identifier carried in from outside, naming history this repository does not contain. It
remains in `platform_freeze/version.py` as `FREEZE_COMMIT` because it is the recorded
origin of the freeze, and removing it would erase the only trace of where the values came
from. It is not evidence. Nothing may be verified against it, and a future reader who finds
it should expect it to resolve nowhere.

`eb5ff947` is the reachable commit that introduced the adopted content. It is the earliest
point at which this repository can speak about these trees at all, and every assertion in
this ADR is made against it or later.

## Decision

1. **Adopt** the current tracked contents of `enterprise_validation_pilot`,
   `comparative_governance_benchmark` and `provider_heterogeneity_validation` as this
   repository's behaviour-tree baseline, hashed under the ratified tracked-`*.py` V1
   algorithm.
2. **Update** the derived `manifest_digest`, which follows arithmetically from (1).
3. **Verify** the behaviour hashes from now on. Adoption without verification would repeat
   the defect at a different value.

**`enterprise_validation_pilot`**

- superseded pin `9241f73c57fa5b9ba5186046caf714e93a3131b1384a7a06f69a5c9bbdf978af`
- adopted baseline `71fe8c32f44567e3ca66e04d72ff8279ebddbd6ecee434ce78ad92d7fdfcf180`

**`comparative_governance_benchmark`**

- superseded pin `827ed95f7ae21abe8500a8b66d14de9a44a12b7048806a29094619c52da1e662`
- adopted baseline `8cfd88bc8378c6c3de21ec314b278ebf7ebecda8b1dc4c6bd38b0b7f7ce9d60c`

**`provider_heterogeneity_validation`**

- superseded pin `85c35cba7ee55dce6e4fd73fd396e172bbdcbd257d8d7f5e5b8bd3a741e49c49`
- adopted baseline `d09ee616b9f6d060c3b0598f1eb2abc5f07f2c9d6393b43239574c861286acc4`

**`manifest_digest`** (derived)

- superseded `05fdb1caace9216a9b42b979c66eb144e17d8a0032aae3500ab668a446094402`
- adopted `df0c61f4d01fef31251ee78f8803b1c7329e255257e193334be587d22cc3b9ee`

The three adopted values are reproducible from the working tree by
`tree_hash(<name>)` at `HEAD`, and the manifest reproduces its own digest.

## Verification, and why exactness

`verify_manifest` now requires the **expected key set exactly** and separates the four ways
it can be violated: `missing_keys`, `extra_keys`, `mismatched_keys`, `uncomputed_keys`. A
plain equality check already fails on all four, but reports only "not equal", and the
distinctions carry different meanings — a vanished key is a coverage regression, an
appeared key is an unratified widening, a moved digest is a content change.

The `missing_keys` case is the one that motivated exactness. Under equality alone, dropping
a key from the manifest *and* from `BEHAVIOUR_TREES` leaves two equal mappings and a tree
silently outside the freeze. Requiring the key set against `V.BEHAVIOUR_TREES` makes the
coverage itself the thing being asserted.

`behaviour_tree_hashes` is reported by the CLI beside the other manifest checks but is
deliberately **not** added to `run_verification`'s `checks` dict: `substantive_digest` is
computed over that dict alone and is pinned as a literal in
`packages/benchmark-registry-authority/verify_br1_freeze_matrix.py` and across the audit
records, so a twelfth entry would move a pinned value for a reporting reason. The verdict
was already gated on it through `manifest_check["passed"]`; what was missing was the name
of the failure, not the failure.

The CLI's per-check reporting was itself misleading and is fixed here. It read `passed`
with a default of `True`, while every manifest-derived check reports `ok` — so a moved tree
hash printed a `FAIL` header above a full column of green lines and left the operator
nothing to read. Measured before the fix: a one-comment edit to
`enterprise_validation_pilot/__init__.py` produced `FAIL` and exit status 1 with all eleven
checks printing `ok`.

Four negative controls in `platform_freeze/tests/test_freeze.py` assert that a tracked
behaviour-file modification (parametrized over all three trees), a missing key, an extra
key and an incorrect digest each fail **both** surfaces — `verify_manifest` against the
stored manifest, and the `platform_freeze.verify` CLI. Three mutations confirm they can
fail: removing the check entirely, weakening it to compare values without the key set, and
reverting the CLI predicate each turn tests red.

## Consequences

- A behaviour tree can no longer be edited without the freeze going red. That is the
  intended cost; these trees are frozen.
- The adopted baseline is only as good as the content at `eb5ff947`. This ADR asserts that
  the content is what this repository has always held, **not** that it is what the foreign
  freeze intended.
- `FREEZE_COMMIT` remains unverifiable. Any future work that needs a checkable freeze
  origin must establish a new one against a reachable commit; it cannot repair `5ae4f70`.

## Recorded, not fixed

`platform_freeze/classify_change.py` diffs against `5ae4f70..HEAD` and therefore cannot
run at all — `git` answers `unknown revision`. `test_classify_change_reports_evidence`
fails on that today, at `HEAD` and after this change alike; it is the same foreign
provenance surfacing in a second place. `[G]`

It is left as it is. Repairing it means choosing a new freeze origin, which is an owner
decision about what the freeze is anchored to and not a consequence of adopting the
behaviour-tree content. Three further pre-existing failures in
`platform_freeze/tests/test_freeze.py` — `test_hiring_baseline_discovery`,
`test_documentation_completeness`, `test_platform_boundary_and_gap_docs_have_content` —
are unrelated to the freeze values; the last two look for governance documents at paths
that moved under `Project_documentation/` without the tests following, a move
`platform_freeze/verify.py::_docs_presence` did track. `[V]` for all four being red before
this change: measured on a detached worktree at `HEAD`, which fails five tests, the fifth
being `test_stored_manifest_verifies` — the behaviour-hash drift this ADR corrects.
