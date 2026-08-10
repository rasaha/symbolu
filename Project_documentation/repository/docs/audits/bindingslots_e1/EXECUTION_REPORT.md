# Explicit-key semantic memory (E1) — execution report

**Primary verdict: `EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`**
**Always co-emitted: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.**
**On pass, additionally: `INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED`.**

A bounded, preregistered B0-vs-E1 capability probe run under strict discipline (bounded dev-calibration
plan committed before selection; mechanical config selection; effect-size gates; fresh blind final
seeds). **Not** a repair of anonymous BindingSlots, **not** a reliability requirement (the external
table already provides reliability), and **KDA remains blocked**. The verdict reconstructs mechanically
from committed evidence; all artifact hashes match; the frozen `abc.json` (`b31989a3…`) is unchanged.

## Process discipline (important)
- A **bounded development-calibration plan** (`DEV_CALIBRATION_PLAN.md` / `dev_calibration_plan.json`)
  was committed and pushed **before** the selection run: exact dev seeds (500–502), a fixed candidate
  set `{C1..C4}` (max 4), max runs/steps/wall-clock/budget, and a mechanical selection rule.
- The rule (`run_dev_selection.py`) selected **C1** = `steps=1200, tau=0.07, train_no_match_frac=0.30`
  (mean dev addressing 1.000), **overriding** an earlier hand-guess — the intended behaviour of a
  mechanical selector.
- **Gates are absolute competence bars** grounded in the frozen B0 baseline (anonymous slots at chance
  ≈0.031) and a meaningful minimum effect size (improvement over B0 ≥ 0.50), **not** thresholds set at
  observed dev performance (`GATE_RATIONALE.md`).
- The final cohort uses **fresh seeds `[3140–3144]`**, disjoint from V100 seeds (28–32), dev seeds, and
  the **burned** seeds `[2028–2032]` (observed in an earlier premature, non-preregistered run and
  explicitly discarded as the final cohort).

## Determinism & integrity (pre-reserved gates, both passed)
- **Determinism:** repeated dev fixture byte-identical (E1+B0 param hashes + metrics equal).
- **Leakage/shortcut suite `all_pass`:** zero query↔key surface-token overlap; disjoint identity pools;
  eval identities unseen in training; no value token in any key; a **lexical-overlap matcher scores at
  chance** (surface hashing cannot solve the task); no external-table import in E1 inference.

## Reserved go/no-go (final pool, 5 fresh seeds, config C1)

| seed | E1 G1 addr | E1 G1 e2e | B0 G1 e2e | no-match false-accept | all gates |
|---|---|---|---|---|---|
| 3140 | 0.993 | 0.927 | 0.027 | 0.140 | ✅ |
| 3141 | 1.000 | 0.947 | 0.033 | 0.173 | ✅ |
| 3142 | 0.993 | 0.947 | 0.027 | 0.160 | ✅ |
| 3143 | 1.000 | 0.947 | 0.047 | 0.107 | ✅ |
| 3144 | 1.000 | 0.907 | 0.033 | 0.147 | ✅ |
| **all** | **≥0.99** | **~0.93** | **~0.03** | **≤0.17** | **5/5** |

Held-out addressing (mean across seeds, E1): unseen-identity **0.997**, paraphrase **0.996**, hard-names
**0.993**, same-entity/diff-attribute **0.999**, recombined **0.995**, stable **0.997**. No-match recall
≈0.85, precision ≈0.95. **Mean E1-over-B0 improvement = 0.901**; worst-seed G1 = 0.993. B0 (anonymous
slots) is at chance on every generalization split and has no abstention.

## What this supports (only)
"The frozen E1 explicit-key dual-encoder bundle learned semantic episode-local key matching with hard
top-1 value retrieval **more reliably than the frozen anonymous BindingSlots baseline** at the
preregistered ~32-key density and held-out generalization conditions." It does **not** establish which
component caused the improvement (a bundle test), repair of anonymous BindingSlots, arbitrary capacity,
versioning, production readiness, long-context reasoning, external-table replacement, or KDA readiness.
See `LIMITATIONS.md`.
