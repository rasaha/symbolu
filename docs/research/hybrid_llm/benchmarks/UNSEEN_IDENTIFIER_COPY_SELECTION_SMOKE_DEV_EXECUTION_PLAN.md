# Unseen-identifier copy/selection — smoke/development execution plan (DRAFT, docs-only)

**Documentation-only. No execution, generation, training, or seed consumption in this session.**
This plan makes a *future* smoke/development run precise and bounded. It authorizes nothing beyond
the companion `…_SMOKE_DEV_EXECUTION_AUTHORIZATION.md`. Reserved final seeds 90760–90764 remain
forbidden throughout.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Decision 1 — Frozen execution commands (future; fail-closed; unexecuted here)
The merged package exposes the building blocks a future smoke/dev run would call (verified present
and importable, **not run**): `runner.build_cohort(seed, cohort, token)`,
`runner.serialize_cohort(...)`, `shortcuts.shortcut_precheck(...)`, `manifest.*` digest utilities,
`trainer.train_in_memory(...)` (reused frozen recipe), and `runner.enter_final_phase(...)` (final
phase — **not used** for smoke/dev). `runner.main` is intentionally fail-closed and raises. A future
authorized step would add a thin argparse wrapper over these; no such CLI is invoked now. Every
command below is fail-closed: a reserved seed without a valid execution token raises
`ExecutionNotAuthorized` at the data-generation primitive **and** the runner (guard strengthened in
PR #1372). **No command includes a final seed.**

| Future command (illustrative) | Building block | Guard |
|---|---|---|
| smoke identifier pools / dataset | `build_cohort(9070, cohort, <smoke-token>)` | fail-closed until a smoke token exists |
| smoke shortcut baselines | `shortcut_precheck(<smoke cohort>)` | fixture-safe; no reserved final |
| smoke training | `train_in_memory(model, encoded, seed=<sub_seed(9070,'batch')>)` | requires smoke authorization |
| smoke evaluation / replay | greedy decode + `parse` + `metrics` | deterministic |
| smoke manifest | `manifest.*` actual digests | required-value fingerprints |
| development pools/dataset/precheck/train/eval/replay | same with seeds 9071–9073 | requires development authorization |

The draft verifies the commands are **syntactically supported by the merged package** (the functions
exist and import cleanly); it does **not** run them.

## Decision 2 — Frozen run matrix
- **smoke:** seed **9070**; **development:** seeds **9071, 9072, 9073**; **final:** none.
- one model recipe · one representation · one tokenizer · one optimizer · one task configuration ·
  splits **C1–C8** · **no intervention arm**.
- Derived (fixed here, from the frozen recipe and split counts):
  - training runs = **1 (smoke) + 3 (development) = 4**;
  - updates per run = **2000** (frozen);
  - aggregate optimizer updates = **4 × 2000 = 8000**;
  - expected checkpoints = **4** (one final checkpoint per run);
  - expected manifests = **4** (one per run) + 1 environment manifest per phase;
  - expected prediction-trace sets = **4** (per-example, all splits/cohorts per run);
  - maximum wall-clock = **24 h** (frozen ceiling; realistic projection ≪ that — the frozen
    recipe trains ~1–2 min/run on CPU);
  - storage budget = small (few MB of JSON traces/manifests per run; no large checkpoints beyond
    the 209,728-parameter model state).
- No value is inferred during a future run; all are fixed here.

## Decision 3 — Frozen scientific-cohort generation order (future)
Permitted order (each step gated; development requires a recorded smoke-integrity pass):
1. environment manifest → 2. source/config/tokenizer hash verification → 3. seed-guard
verification → 4. smoke identifier pools → 5. smoke dataset → 6. smoke shortcut baselines →
7. smoke training → 8. smoke evaluation → 9. smoke deterministic replay → 10. smoke integrity report
→ 11. smoke audit → **12. only if smoke passes:** development identifier pools → 13. development
datasets → 14. development shortcut precheck → 15. development training → 16. development evaluation
→ 17. development replay → 18. development evidence report → 19. independent development-evidence
audit. **Development must not begin automatically because smoke code exits 0** — it requires an
explicit recorded `SMOKE_INTEGRITY_PASS`.

## Decision 4 — Frozen pre-execution checks (all required before smoke)
Authoritative default clean · correct merge ancestry · protocol-lock digest matches ·
implementation-authorization digest matches · **implementation audit verdict = confirmed** · model
source hashes match · **parameter count = 209,728** · scientific seeds still unused · fixture outputs
removed or isolated · environment recorded · disk/memory budget sufficient · no training process
running · no stale checkpoint · no stale run directory · execution-authorization record/token
present. **Any failure blocks smoke.**

## Decision 5 — Frozen smoke gates (integrity/feasibility, NOT scientific)
Smoke requires: command completes without infrastructure failure · all C1–C8 cohorts generated ·
no pool collisions · no train/dev/final contamination · serializer byte stability · manifest
complete · all required digests present · parser categories operational · checkpoint readable ·
deterministic replay exact · no reserved-final artifact · no protocol deviation · wall-clock
projection ≤ frozen budget · shortcut machinery produces valid baselines and chance values.
**Smoke does NOT require positive model accuracy.**

Smoke outcomes (exactly one): `SMOKE_INTEGRITY_PASS` · `SMOKE_IMPLEMENTATION_DEFECT` ·
`SMOKE_PROTOCOL_DEVIATION` · `SMOKE_RESOURCE_BLOCKED` · `SMOKE_NONDETERMINISTIC` ·
`SMOKE_AUTHORIZATION_VIOLATION`. **Only `SMOKE_INTEGRITY_PASS`** may permit a later
development-execution authorization/continuation, per the frozen lifecycle.

## Decision 10 — Frozen stopping rules
Stop immediately if: any reserved final seed is touched · source hash differs · parameter count
differs · protocol digest differs · a shortcut anomaly exceeds its bound · identifier pools overlap ·
the serializer changes · deterministic replay fails · a manifest is incomplete · an artifact path is
contaminated · an unauthorized process starts · the wall-clock budget cannot be met · implementation
code changes during execution. **Do not proceed from smoke to development without
`SMOKE_INTEGRITY_PASS`. Do not proceed from development to final authorization within this session.**

## Decision 6 — Frozen development gates
Development must verify: all three seeds complete · deterministic replay · manifest completeness ·
**no shortcut baseline above its frozen bound** · no task-construction imbalance · no identifier
leakage · no position leakage · no output-template leakage · no seed collision · no protocol
deviation · resource use within budget. Development results are labeled
**`DEVELOPMENT_ONLY_NOT_FINAL_EVIDENCE`**; **no final capability verdict may be emitted.**

If a shortcut anomaly occurs: block further execution · do **not** inspect final seeds · diagnose
using development evidence only · any protocol/implementation change invalidates affected
development evidence and requires a corrective PR + fresh development authorization.

## Decision 7 — Frozen shortcut precheck (aggregation contract explicit)
Future shortcut artifacts: per-task chance · per-split heuristic score · per-seed heuristic score ·
aggregate heuristic score · threshold (**chance + 0.05**) · competence-floor comparison · blocking
status. **Aggregation contract (explicit, so execution code never infers it):**
- chance is computed **mechanically per split** (1 / candidate-count for selection splits);
- each heuristic is scored **per split, per seed**;
- the gate is evaluated on the **per-split score pooled across the development seeds** (9071–9073)
  to reduce single-cohort sampling noise, and additionally reported per seed;
- a split fails if its pooled score exceeds chance + 0.05 **or** falls at/above the learned
  competence floor.
This matches the merged implementation (`shortcuts.shortcut_scores` computes per-split baselines).
A shortcut precheck must occur **before** development results can be accepted and **before** any
future final authorization can be drafted.

## Decision 11 — Frozen development-report vocabulary
Allowed development-status outputs: `DEVELOPMENT_INTEGRITY_PASS` · `DEVELOPMENT_SHORTCUT_BLOCKED` ·
`DEVELOPMENT_IMPLEMENTATION_DEFECT` · `DEVELOPMENT_PROTOCOL_DEVIATION` ·
`DEVELOPMENT_RESOURCE_BLOCKED` · `DEVELOPMENT_NONDETERMINISTIC` ·
`DEVELOPMENT_AUTHORIZATION_VIOLATION`. **Do not emit** `UNSEEN_IDENTIFIER_COPY_SELECTION_CONFIRMED`,
`UNSEEN_IDENTIFIER_SELECTION_FAILED`, `UNSEEN_IDENTIFIER_GENERALIZATION_FAILED`,
`UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND`, or any final scientific verdict. Development metrics
may be reported descriptively but remain **non-final**.
