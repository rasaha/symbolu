# Unseen-identifier copy/selection — fresh smoke/development rerun under the corrected gate (post-#1379)

**Scope:** re-run smoke `9070` + development `9071–9073` under the merged corrected shortcut gate and
re-evaluate the development result. **Final seeds `90760–90764` were NOT touched; `--phase final` was
never invoked; no capability verdict is emitted.** Development emits only frozen `SMOKE_*`/`DEVELOPMENT_*`
namespace verdicts.

## 1. Provenance
| Item | Value |
|------|-------|
| PR #1379 state | **already merged** by `rasaha` at 2026-08-07T03:20:00Z |
| PR #1379 merge commit | `ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4` (parents `b73a9f1e` + `23b90c02`) |
| Authoritative default-branch commit | `ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4` |
| Audited corrective head | `23b90c0256658014cd5f9f5a2943279c99e2aad8` (byte-identical `shortcuts.py` on default) |
| Corrected `shortcuts.py` sha256 | `d189bb9e1922ec92ab5cd2fdd095518a237afdac5cd4399c3cccc98175e52c55` |
| Fresh authorization record | `…_SMOKE_DEV_REAUTHORIZATION_POST_1379.md` (binds to `ed95bff6`) |

## 2. Environment
Python 3.11.15 · torch 2.13.0+cu130 (CPU, `cuda_available=False`) · Linux x86_64 (glibc 2.39).
Frozen recipe source hashes (unchanged): `model.py` `39a2a128…`, `tokenizer.py` `1849fd1f…`,
`trainer.py` `ea0af36e…`, recipe `config.py` `324be79d…`. Frozen parameter count 209,728.

## 3. Pre-run integrity
Working tree clean at `ed95bff6`; fixture suite **120 passed**, frozen-recipe suite **23 passed**;
seed-role map intact (`smoke=9070`, `development=9071–9073`, `final=90760–90764` reserved,
`fixture=993000–993004`). No reserved seed used for debugging.

## 4. Determinism / integrity evidence
Every fresh (seed, cohort) reproduced the committed prior run **bit-for-bit**: initialization,
batch-order, checkpoint-parameter, prediction (seen+unseen), dataset (seen+unseen), and identifier-pool
digests **all match**, and `first_loss`/`final_loss` match exactly — across a different torch version.
This confirms (a) exact determinism and (b) that the #1379 correction touches **only** the shortcut
decision, not training/evaluation.

## 5. Smoke result — seed 9070
`final_loss = 0.6111193895339966` (identical to prior); wall-clock 36.96 s; all integrity gates pass;
corrected shortcut precheck `seen_all_pass = unseen_all_pass = True`.
**Verdict: `SMOKE_INTEGRITY_PASS`** (Decision 5: smoke tests machinery/determinism/integrity, not accuracy).

## 6. Per-seed development execution
| seed | wall-clock s | first_loss | final_loss | shortcut seen | shortcut unseen |
|------|-------------|-----------|-----------|---------------|-----------------|
| 9071 | 38.57 | 5.277719 | 0.889509 | pass | pass |
| 9072 | 39.18 | 5.312153 | 0.384856 | pass | pass |
| 9073 | 41.38 | 5.293599 | 0.931015 | pass | pass |

## 7. Corrected shortcut-gate reconstruction (pooled across 9071–9073)
Chance `= 1/3`; practical margin `bound = chance + 0.05 = 0.3833`; **family size = 72** comparisons
(6 selection splits C2–C7 × 12 baselines) per cohort; exact one-sided binomial upper tail;
Holm–Bonferroni FWER `= 0.05`.

- **Seen:** 8 baselines exceed the practical margin, **0 are Holm-significant → 0 block.** Smallest
  binomial p among them `= 0.0253` (73/180), vs. the strictest Holm threshold `0.05/72 = 0.00069`;
  even step-down's first (loosest) comparison at rank 1 uses `0.05/72`, so none is rejected. **PASS.**
- **Unseen:** 1 baseline over margin (`C7:last_target`, 73/180, binom p `0.0253`), **0 block. PASS.**
- **Combined development shortcut result: PASS** (no comparison satisfies both legs).

These are exactly the marginal-noise baselines the previous flat `p̂ > chance + 0.05` rule
false-blocked (`DEVELOPMENT_SHORTCUT_BLOCKED`, superseded). Under the sampling-aware corrected gate the
false block disappears without weakening a genuine leak (a real leak yields a tiny binomial tail and
still blocks). Full per-comparison table: `gate_reconstruction_corrected.json`.

## 8. Development science — seen vs unseen exact-match (descriptive, NON-FINAL)
Mean exact-match over seeds 9071–9073 (60 examples/split/seed):

| split | condition | seen exact | unseen exact | gap |
|-------|-----------|-----------:|-------------:|----:|
| C1 | direct-copy | 0.7944 | 0.0056 | 0.7888 |
| C2 | relation/binding | 0.4667 | 0.0000 | 0.4667 |
| C3 | evidence lookup | 0.5500 | 0.1611 | 0.3889 |
| C4 | relation (position-controlled) | 0.4167 | 0.0000 | 0.4167 |
| C5 | relation (lexical decoys) | 0.5000 | 0.0000 | 0.5000 |
| C6 | relation (seen-pool control) | 0.4000 | 0.0000 | 0.4000 |
| C7 | relation (unseen-pool generalization) | 0.4556 | 0.0000 | 0.4556 |
| C8 | no-match / abstention | 1.0000 | 1.0000 | 0.0000 |

- **Direct-copy** collapses on unseen identifiers (0.79 → ~0.006).
- **Relational/binding** (C2, C4, C5, C6, C7) is at/near **0.0** on unseen (from 0.40–0.50 on seen).
- **Evidence lookup** (C3) is the only positive unseen signal (0.16), still far below seen (0.55).
- **Abstention** (C8) is perfect on both cohorts (1.0) — the model correctly refuses missing keys, but
  this is a constant-gold behavior that carries no copy/selection competence.
- **No-match/abstention** carries no fabrication into positive splits on seen (`fabricated` low); on
  unseen, positive-split outputs are dominated by out-of-context fabrication (C2/C4/C6/C7 fabricated
  ≈ 0.54–0.63), i.e. the model emits invented identifiers rather than transferring the rule.
- Per-seed variability is small (e.g. C1 unseen exact sd ≈ 0.008; all relation unseen exact sd = 0).

**Interpretation (development-only, not a capability claim):** the seen→unseen gap is large and
consistent; the descriptive evidence indicates the model does **not** transfer the relational rule to
identifiers unseen during training. This is the hypothesis a final evaluation exists to test
rigorously; it is deliberately **not** asserted as a final capability verdict here.

## 9. Verdicts (frozen namespaces only)
- Smoke: **`SMOKE_INTEGRITY_PASS`**
- Development integrity gates (all seeds completed, deterministic replay, manifest completeness,
  **corrected shortcut gate PASS**, no seed collision, resources within budget): **all pass** →
  **`DEVELOPMENT_INTEGRITY_PASS`**.

The frozen development namespace defines **no capability/competence floor** (capability is a final-only
verdict); development therefore clears its integrity prerequisite for final evaluation. Whether the
capability itself exists is undetermined here and, on the descriptive evidence, doubtful — that is for
a separately-authorized final phase to decide.

## 10. Final-seed status
`--phase final` never invoked; seeds `90760–90764` never generated, inspected, or consumed; no final
run directory or artifact exists. **Final cohort remains PROHIBITED and untouched.**

Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.
