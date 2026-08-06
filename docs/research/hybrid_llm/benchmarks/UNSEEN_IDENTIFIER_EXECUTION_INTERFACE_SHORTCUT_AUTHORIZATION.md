# Unseen-identifier execution-interface & shortcut completion — authorization (DRAFT, docs-only)

**Documentation-only. No code is written, no execution performed, no scientific seed consumed.**
Maximum state this session: **`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_AUTHORIZATION_DRAFT_READY`**.
This draft does **not** emit `IMPLEMENTATION_AUTHORIZED`, `EXECUTION_AUTHORIZED`,
`SMOKE_EXECUTION_AUTHORIZED`, `DEVELOPMENT_EXECUTION_AUTHORIZED`, `FINAL_EXECUTION_AUTHORIZED`, or
any scientific verdict.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Prerequisite
The blocker record (`…_EXECUTION_INTERFACE_SHORTCUT_BLOCKER.md`) established
`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_REQUIRED` on default `773a7c93`: PR #1373 (smoke/dev
execution authorization) is blocked because its commands need an execution interface the merged
fixture-only package lacks, and the shortcut suite implements 8 of 12 frozen baselines.

## Authorization statement (draft)
> Once independently audited and merged, this record authorizes only implementation of the missing
> execution interface, shortcut-suite completion, fixture-only tests, and integrity CI. It does not
> authorize generation or use of smoke seed 9070, development seeds 9071–9073, or final seeds
> 90760–90764. It does not authorize training, evaluation, replay, or scientific cohort generation.

## Permitted corrective implementation scope (a later merged authorization may permit ONLY)
1. CLI and executable entry-point implementation; 2. execution authorization-record schema and
validation; 3. cohort-build orchestration; 4. frozen-model training orchestration; 5. checkpoint
handling; 6. evaluation and greedy-decoding orchestration; 7. parser and metric orchestration;
8. deterministic replay orchestration; 9. manifest and per-example trace emission; 10. explicit
output-path handling; 11. the four missing shortcut baselines; 12. exact shortcut aggregation;
13. competence-floor comparison; 14. fixture-only tests; 15. integrity CI strengthening;
16. bounded documentation updates.

## It must NOT permit
scientific execution · scientific cohort generation · use of seed 9070 · use of seeds 9071–9073 ·
use of seeds 90760–90764 · protocol changes · numeric-gate changes · model-recipe changes ·
tokenizer changes · candidate-index output · constrained decoding · candidate-ranking objectives ·
pointer/copy heads · curriculum changes · capacity changes · pretrained substitution · BindingSlots ·
E1 memory · multi-hop work · temporal work · production integration.

## Draft status
See `…_EXECUTION_INTERFACE_SHORTCUT_IMPLEMENTATION_PLAN.md` (Decisions 1–12) and
`…_EXECUTION_INTERFACE_SHORTCUT_CHECKLIST.md`. When complete this package emits only
**`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_AUTHORIZATION_DRAFT_READY`** — the corrective scope and
controls are fully specified for independent review; **no implementation or execution is authorized
by this draft.**
