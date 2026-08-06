# Unseen-identifier copy/selection — implementation-authorization (DRAFT, documentation-only)

**Documentation-only. No code is written, no dataset generated, no model trained, no seed consumed,
no execution authorized in this record or session.**

Maximum state this session: **`IMPLEMENTATION_AUTHORIZATION_DRAFT`**. This draft does **not** emit
`IMPLEMENTATION_AUTHORIZED`, `EXECUTION_AUTHORIZED`, or any scientific result verdict.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Authorization statement (draft)
> Once independently audited and merged, this record authorizes implementation of the frozen
> unseen-identifier diagnostic only. It does not authorize dataset generation beyond unit fixtures,
> model training, smoke execution, development execution, or reserved final execution.

## PR #1369 audit and merge record (prerequisite for this package)
The protocol lock was independently audited from live Git/GitHub ground truth and merged before this
authorization package:
- **Decision:** `MERGE_READY_AFTER_SCOPED_CORRECTIONS` → merged.
- **Mechanical state at audit:** open, draft, `mergeable_state: clean`; base = default `872c034c`
  (contains merged PR #1368); **documentation-only** (5 files, +404/−11); **7/7 CI checks green** on
  the latest head; **0 unresolved review threads**.
- **Content verified live:** emits only `UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCKED`;
  implementation/execution unauthorized; two-axis diagnosis (copy-vs-selection with the
  copy-masks-selection rule; seen-vs-unseen with the mislabel guard) and iterative loop; C1–C8 exact;
  exact-ID output with **no** candidate-index / constrained decoding / intervention arm; C8 scored
  separately with no constant-gold in the primary; one representation-neutral format; character-
  visible disjoint identifiers; frozen numeric gates; shortcut policy with a hard pre-reserved
  precheck; frozen seeds (smoke 9070 / dev 9071–9073 / final 90760–90764, not consumed); compute
  limits; claim boundary; standing invariants.
- **Model recipe re-verified from merged source:** 209,728 params; d_model 64 / 2 layers / 4 heads /
  d_ff 256 / vocab 200; AdamW 3e-4, batch 8, 2000 updates; recipe source hashes match the lock
  (`config.py 324be79d…`, `tokenizer.py 1849fd1f…`, `model.py 39a2a128…`, `trainer.py ea0af36e…`).
  No discrepancy.
- **Scoped correction applied before merge (documentation-only):** froze a total-order,
  first-match-wins **verdict precedence** for co-occurring failures in Decision 8 (integrity →
  resource → copy/generalization base → selection → evidence → abstention → confirmed), with worked
  cases; `COPY_ONLY_PARTIAL` reconciled as a synonym of `SELECTION_FAILED`, not a second primary.
- **Merge commit:** `ec9145f2820948cd1af8c69a19f48d70da050fd3` (reachable from the authoritative
  default; default synchronized; clean working tree).

## What a later merged authorization would permit — and would NOT
A future, separately-audited-and-merged authorization may permit **only** code implementation and
**fixture-only** tests (Decisions 1–11 of the implementation plan). It must **not** permit:
generating the smoke cohort · generating development cohorts · generating reserved final cohorts ·
training · evaluating scientific metrics · consuming seed 9070 · consuming seeds 9071–9073 ·
consuming seeds 90760–90764 · changing the locked protocol · implementing any intervention.

Unit fixtures must use a **separately reserved testing seed namespace** (`993000–993004`,
mechanically verified unused; see the implementation plan), never the reserved diagnostic seeds.

## Draft status
See `UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_PLAN.md` (Decisions 1–12) and
`…_IMPLEMENTATION_CHECKLIST.md`. When the design is complete this package emits only:
**`UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_AUTHORIZATION_DRAFT_READY`** —
*the implementation scope and controls are fully specified for independent review; no implementation
or execution is authorized by this draft.*
