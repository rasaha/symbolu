# Unseen-identifier execution-interface & shortcut-suite blocker record

Documentation-only. Records the live blocker keeping PR #1373 (smoke/development execution
authorization) unmerged. Reconstructed from live Git/GitHub and merged source; no code changed, no
scientific execution performed.

## Blocker conclusion
**`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_REQUIRED`.** PR #1373's execution plan freezes commands
that require an execution interface the merged fixture-only implementation does not provide, and the
merged shortcut suite implements only 8 of the 12 frozen baselines. The blocker is not a
documentation ambiguity; it requires a separately-authorized implementation of the execution
interface and shortcut completion.

Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

## Live state (verified)
- Authoritative default: `773a7c932b8780caa12559e15f7c7f9fced16f59`.
- PR #1373: open · draft · unmerged · `mergeable_state: clean`; head
  `3ddb8fe9ad3211e27ac5a6865431d30448e8c9a0`; base = default; **documentation-only** (5 files,
  +357/−4); CI 7/7 green; 0 review threads. **PR #1373 remains unmerged and is not modified.**

## Existing execution capabilities (merged `experiments/unseen_identifier_copy_selection/`)
`runner.build_cohort` (data-gen, fail-closed) · `runner.serialize_cohort` ·
`runner.enter_final_phase` (final-phase guard) · `runner.main` (**raises** `ExecutionNotAuthorized`) ·
`shortcuts.shortcut_precheck`/`shortcut_scores` (single-cohort, per-split) · `metrics.*` (pure) ·
`verdict.evaluate` (gate on synthetic inputs) · `manifest.*` (digest utilities) · primitive-level
reserved-seed guards in `tasks`/`identifiers`.

## Missing execution capabilities (verified absent)
- real CLI entry point / `argparse` / `__main__`;
- executable subcommands (build-cohort / train / evaluate / replay / shortcut-precheck /
  assemble-manifest);
- one-explicit-seed argument handling and authorization-record validation at a command boundary;
- frozen-model **training orchestration** (encode cohort → `train_in_memory` → checkpoint);
- checkpoint writing to disk;
- **evaluation + greedy decoding** runner (model → decode → parse → per-example predictions);
- parser/metric run orchestration;
- **deterministic replay** command;
- **run-manifest assembly** and **per-example trace emission** to explicit output paths;
- explicit output-directory control;
- **cross-development-seed shortcut aggregation** (`shortcut_scores` operates on one cohort list).

No `cli.py` / `__main__.py` / `training.py` / `evaluation.py` / `replay.py` / `evidence.py` exists.

## Shortcut-suite gap (verified)
Protocol-lock Decision 9 requires **12** baselines; the merged `shortcuts._baselines_on` implements
**8**: first-target · last-target · middle-target · most-frequent-target · lexical-similarity ·
prefix-match · character-overlap · constant-abstention.
**Missing 4:** source–target co-occurrence · seen-ID frequency · output-template leakage ·
task-label leakage. All four are mechanically definable from the merged protocol and existing task
metadata (`pairs`, `cohort`, `task_name`, `seen_unseen`), so no baseline-definition block applies.

## Confirmation
No scientific execution occurred: no smoke/development/final cohort generated, no model trained or
instantiated for execution, no scientific seed consumed (9070 / 9071–9073 / 90760–90764 untouched),
no reserved final pool inspected. PR #1373 is unchanged and unmerged.

## Required corrective lifecycle
1. this documentation-only authorization draft opened → 2. independent audit (separate session) →
3. authorization PR conditionally merged → 4. authorized implementation of only the execution
interface + 4 missing shortcuts + fixture tests + CI (separate session; draft PR, stop) →
5. independent audit of that implementation → 6. conditional merge → 7. PR #1373 updated/replaced
with real executable commands → 8. independent audit of the updated smoke/dev authorization →
9. conditional merge → 10. only then may smoke seed 9070 be considered. **This session performs only
step 1's authoring.**
