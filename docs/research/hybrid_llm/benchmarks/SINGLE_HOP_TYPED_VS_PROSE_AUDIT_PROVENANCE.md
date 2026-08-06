# Typed-vs-prose result — provenance & branch-extraction audit (Stage 1)

Reconstructed from Git ground truth (not from prior summaries or branch names). All hashes are
verified with `git rev-parse` / `git merge-base` against the fetched remote.

## Authoritative references
| Ref | Full SHA |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default tip | `0c63d1f2400716ab23249c9d76805ac517e70956` ("Merge PR #1363: preregister typed-vs-prose single-hop benchmark (docs-only)") |
| Reported result head | `422ab3e51ab669231dee1160f128364d4e5d58b4` ("results(typed-vs-prose): execute frozen protocol -> ADVANTAGE_NOT_FOUND") — **exists and reachable** |
| Reported earlier head | `cc86d17f8178ef6e01f84f4e7fc1d2725979b9e3` |
| Scoped audit branch | `claude/typed-vs-prose-result-audit` @ `422ab3e5` (new, correctly named) |

## Commit-graph findings
- **`merge-base(default, result) == default tip** (`0c63d1f2`)**. Default is a **direct ancestor**
  of the result. The result is exactly **45 commits** ahead of default, and **0** commits exist on
  default that are absent from the result (`git rev-list --left-right --count` → `0  45`).
- **All 45 commits are typed-vs-prose benchmark work** (protocol-lock lineage → implementation
  authorization → implementation package → the three execution commits). **No merge commits**
  (`git log --merges default..result` → empty). **No rebase/force-push discontinuity** in this
  range (linear, single parent chain).
- **`cc86d17f` is itself an ancestor of default.** Therefore the previously-reported
  "≈296-commit fast-forward" of the mis-named branch `claude/bindingslots-confirmatory-...` was
  **advancing a stale branch pointer across already-merged default history (≈251 commits) plus the
  45 benchmark commits**. No *unrelated new* commit entered relative to default:
  `296 = (cc86d17f → default) 251 + (default → result) 45`. The 296 count was measured against the
  stale branch tip, not against default; against default the scope is 45 commits.

## File-scope findings (diff vs default)
`git diff --name-only default..result` → **33 files, +4910 / −0 (pure addition)**, every path within:
- `experiments/single_hop_typed_vs_prose/**` (implementation, tests fixtures, raw run artifacts),
- `tests/experiments/single_hop_typed_vs_prose/**`,
- `docs/research/hybrid_llm/benchmarks/**`,
- `.github/workflows/typed-vs-prose-implementation-ci.yml`.

**No file outside typed-vs-prose scope** (verified by inverse-grep). No BindingSlots, temporal,
architecture, product, or repository-wide change is present in the range.

## Clean-extraction decision
A cherry-pick surgery is **not required**: because every commit in `default..result` is
benchmark-specific and the diff is a clean additive layer, the scoped extraction is simply a
fresh, correctly-named branch at the same tip with the PR based on default.
- **Original → extracted commit mapping: identity** (all 45 commits retained unchanged; artifact
  bytes and hashes preserved). No commit excluded; none rewritten.
- **Retained:** all 33 benchmark files above.
- **Excluded:** nothing (there was nothing out of scope to exclude).
- The mis-named branch `claude/bindingslots-confirmatory-replication-d117c1` is abandoned for
  review purposes in favor of `claude/typed-vs-prose-result-audit`; both point at identical
  content, so no evidence is altered by the rename.

## Authorization-ordering timeline (UTC-normalized commit dates; ancestry is the authority)
Linear chain, monotonic in time after normalizing mixed author timezones to UTC:
1. `1b8d5d13` / `7b5c9b3d` protocol lock — 03:48Z
2. `687e8269` implementation authorization — 04:56Z (10:26 +0530)
3. `8c4e463d` implementation package — 05:13Z (10:43 +0530)
4. `921d9b8d` harness reconcile — 06:21Z
5. `977f6638` freeze design + driver + **EXECUTION_AUTHORIZATION.md** — 06:40Z
6. `422ab3e5` reserved execution results — 07:07Z

No results artifact commit predates the freeze/authorization commit (`977f6638` precedes
`422ab3e5` both by ancestry and by timestamp). Detailed ordering verification continues in the
Stage-2 authorization audit.

## Stage-1 conclusion
Provenance is clean: default-anchored, 45 in-scope commits, no unrelated work, no merges, identity
extraction. The scoped draft PR is opened against default with this range. Proceed to Stage-2
independent audit under the fix-then-merge policy.
