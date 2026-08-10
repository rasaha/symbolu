# StoryGraph Documentation Canonicalization — Report

**Verdict: `CONTINUE — StoryGraph documentation canonically organized`.**

This phase completes the StoryGraph repository migration by moving all
StoryGraph-owned documentation into an indexed canonical structure, preserving
historical evidence, repairing stale links and commands, adding runnable canonical
examples, and clearly separating runtime package data from repository-only
evaluation and migration evidence. No matching, policy, replay, serialization,
public API, digest, or advisory-authority semantics are changed.

---

## Commits (start → end)

| | |
|---|---|
| Starting commit | `f076fa5b22e0e37395f5e59232dba690f208663c` |
| Ending commit | head of `claude/storygraph-canonical-package-migration-m25c2i` |
| Commits | `5af10e6` move omitted docs · `cd2522f` organize · `54bee90` repair refs · `92a089d` examples · `1ad7ff7` wheel-data + link validation · `9f764b7` move 7th omitted doc · this report |

## Documents moved (git renames, history preserved)

**Seven** StoryGraph-owned documents relocated from `cyber_security/` root into the
package (the six from the finding + a seventh discovered by the §11 re-scan):

| Document | New location |
|---|---|
| COMPOSITE_THREAT_DETECTION_SPEC.md | `docs/architecture/` |
| COMPOSITE_SEQUENCE_RISK_EVALUATION_PLAN.md | `docs/evaluation/` |
| SHADOW_PILOT_REPORT_TEMPLATE.md | `docs/evaluation/` |
| PHASE3_FINAL_EVALUATION_REPORT.md | `docs/evaluation/historical/` |
| HISTORICAL_REPLAY_K8S_CONTRACT.md | `docs/replay/` |
| HISTORICAL_REPLAY_READINESS_CHECKLIST.md | `docs/replay/` |
| **ENFORCEMENT_PROMOTION_CHECKLIST.md** (7th; under-counted earlier — titled "Composite Sequence-Risk Analyzer", referenced by `policy.py`) | `docs/evaluation/` |

## Documents reorganized (the previously-flat 13 → subdirectories)

`docs/` went from a flat dump to: `architecture/` (overview + specs + schemas),
`api/`, `policy-packs/`, `replay/`, `evaluation/` (+ `historical/`), `validation/`,
`reference/`, `limitations/`. The original `docs/README.md` (detailed overview)
became `architecture/CAPABILITY_OVERVIEW.md`; a new canonical index took its place.
New docs added: `docs/README.md` (index), `docs/DOCUMENT_OWNERSHIP.md`,
`docs/api/README.md`, `docs/limitations/KNOWN_LIMITATIONS.md`.

## Documents intentionally retained elsewhere (not moved)

- `Project_documentation/action_gate_cyber/cyber_security/composite_threat_detector/README.md` — legacy-compatibility pointer.
- ActionGate docs at `cyber_security/` (`ACTION_GATE_SPECIFICATION.md`,
  `artifact_story_policy.schema.json`, …) — ActionGate-owned; cross-referenced but
  not StoryGraph-owned.
- Repo-wide audits / platform / product / VC docs that *mention* StoryGraph.
- `docs/migrations/storygraph/` — migration evidence, kept at the repository level
  (not moved into the installable package).

Full table in `packages/capabilities/storygraph/docs/DOCUMENT_OWNERSHIP.md`.

## Historical documents preserved

Evidence/validation/historical reports (`STORY_GRAPH_*_VALIDATION.md`,
`STORY_GRAPH_EVIDENCE_LEDGER.md`, `STORY_GRAPH_FINAL_SPLIT_AUDIT.md`,
`SANITIZED_ENTERPRISE_REPLAY_REPORT.md`, `PHASE3_FINAL_EVALUATION_REPORT.md`,
`MIGRATION_NOTES.md`) were moved **verbatim**. No test counts, verdicts,
timestamps, or claims were rewritten. `PHASE3` received a labeled "preserved
verbatim" note with the current CLI equivalent; nothing in its body was altered.

## Stale references repaired

- **Source** (docstrings/comments/path-constants only, no executable change):
  `model.py`, `__init__.py`, `completion.py`, `prior_runs.py`, `story_corpus_v2.py`,
  `policy.py` doc references → canonical `docs/...` sub-paths; `evidence_chain.py`
  `APPROVED_EVIDENCE_PATHS` doc globs → `docs/evaluation/`; shipped
  `replay_intake/README.md` module/report paths canonicalized.
- **Docs:** current docs' `composite_threat_detector` → `ugence_storygraph` (CLI,
  imports, module paths). Frozen `ctd.*` semantic identifiers left untouched.
- **Links:** 9 broken relative Markdown links fixed (reorg + rename); ActionGate
  cross-references repointed to `Project_documentation/action_gate_cyber/cyber_security/ACTION_GATE_SPECIFICATION.md`.
  `check_doc_links.py` reports **all 30 doc links resolve**.

## Examples added

`examples/{minimal_story_evaluation,proposed_action_evaluation,policy_pack_compilation,replay_smoke}.py`
+ `README.md` — public-API-only, deterministic, synthetic, advisory-only. Executed
by `tests/examples/test_examples_run.py` (in-repo) and by
`verify_storygraph_distribution.py` step [5/5] against the isolated installed wheel.

## Wheel contents before and after

**Unchanged.** Documentation was already outside `src/` and never shipped;
examples are repository-only. The wheel ships exactly the runtime data
(policypack schema+fixture, replay-intake schema/templates, evaluation fixture) and
**no** docs/tests/historical-evidence/migration material — now machine-enforced by
`_check_wheel_content_policy` in the verifier.

## Validation results (§12)

| Check | Result |
|---|---|
| Complete StoryGraph suite | **316 passed** (289 original + 22 compatibility + 5 example) |
| Compatibility tests | pass (in suite) |
| Independent wheel verifier | **PASS** (+ wheel-content policy + examples-on-wheel) |
| Example execution tests | pass (in-repo + on wheel) |
| Documentation-link validation | **PASS** (30 files, all links resolve) |
| Package-data verification | **PASS** (required runtime data ships; repo-only excluded) |
| Digest comparison | **unchanged** — replay `sha-256:0dcf2bc4…`, reference-graph `sha-256:6a77b899…`, pre-registration `sha-256:1f026c7a…` |
| Public API comparison | **unchanged** — 76 symbols |
| Import graph comparison | **unchanged** — only docstrings/comments/doc-path constants edited; no import added/removed |

## Required invariants (§12)

- Original 289 tests still pass ✅ (316 total)
- Added compatibility/documentation/example tests pass ✅
- No frozen digest changes ✅
- No API symbol removal ✅ (76, unchanged)
- No authority change ✅ (advisory-only preserved)
- No source algorithm change ✅ (docs/comments/constants only)
- No duplicate StoryGraph documentation ✅ (git renames; nothing left behind)
- Historical evidence remains reconstructable ✅ (moved verbatim)

## Remaining limitations

- ActionGate cross-reference links use a deep relative path
  (`../../../../../cyber_security/ACTION_GATE_SPECIFICATION.md`); correct but
  brittle if either tree moves — acceptable for a cross-capability reference.
- Examples are repository-only (not shipped in the wheel) by policy; consumers run
  them from a checkout against the installed wheel.

## Rollback procedure

`git revert` the six documentation commits in reverse (`9f764b7 → 1ad7ff7 →
92a089d → 54bee90 → cd2522f → 5af10e6`), or check out the pre-phase commit
`f076fa5`. All moves are git renames and all edits are documentation/comment/
constant-only, so a revert restores the prior layout with no data or evidence loss
and no runtime effect.

---

## Final verdict

**`CONTINUE — StoryGraph documentation canonically organized`.**

This phase completes the StoryGraph repository migration by moving all
StoryGraph-owned documentation into an indexed canonical structure, preserving
historical evidence, repairing stale links and commands, adding runnable canonical
examples, and clearly separating runtime package data from repository-only
evaluation and migration evidence. No matching, policy, replay, serialization,
public API, digest, or advisory-authority semantics are changed.
