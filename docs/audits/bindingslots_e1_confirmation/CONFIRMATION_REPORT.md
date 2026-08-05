# E1 independent confirmation — report

**Primary verdict: `E1_INDEPENDENTLY_CONFIRMED`.**
**Always co-emitted: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.**
**On confirmation, additionally: `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`.** KDA is **not** unblocked.

An independent replication of the merged PR #1351 result. The **exact frozen C1 recipe** (models +
hyperparameters + gates) was reused unchanged; the **task generator, evaluator, leakage suite, and all
seeds were independently rebuilt**. Verdict reconstructs mechanically; artifact hashes match; frozen
`abc.json` (`b31989a3…`) unchanged.

## Independence
- **New vocabulary** (56 entity / 22 attribute primitives, 36 values, 14 filler; new pool salt →
  fresh identity partition), **distinct query template** (attribute-anchored; different filler/ordering),
  **distinct hard-negative profiles**, an **independently re-implemented evaluator** and **leakage
  suite**, and **fresh seeds** (train-episode 71; dev 700–702; final 5140–5144) disjoint from every seed
  used before (V100 28–32, E1 dev 500–502, burned 2028–2032, E1 final 3140–3144, train seed 7).
- Difficulty kept **comparable** to the validated task (3 synonyms/primitive, ~32-key density) so this is
  a fair replication; independence is in content/templates/seeds/evaluator, not difficulty.
- Reused unchanged: the C1 recipe (`steps=1200, τ=0.07, no-match-frac=0.30, batch=48, lr=1e-3, D=64,
  1500 train episodes`, learned null key, contrastive episode-local matching, hard top-1 read) and the
  17 frozen PR #1351 gates.

## Pre-final checks (frozen before the cohort)
Determinism fixture byte-identical; leakage suite `all_pass` (no query/key exact overlap, disjoint
pools, unseen eval identities, no value token in keys, no opaque per-identity id, lexical-overlap matcher
at chance ≈0.05, no external-table import); seed disjointness asserted; final seeds unused before lock.

## Reserved cohort (fresh seeds 5140–5144, config C1)

| seed | E1 G1 addr | E1 G1 e2e | B0 G1 e2e | no-match FA | all gates |
|---|---|---|---|---|---|
| 5140 | 0.987 | 0.913 | 0.033 | 0.140 | ✅ |
| 5141 | 1.000 | 0.927 | 0.020 | 0.220 | ✅ |
| 5142 | 0.993 | 0.953 | 0.047 | 0.167 | ✅ |
| 5143 | 0.993 | 0.940 | 0.027 | 0.107 | ✅ |
| 5144 | 1.000 | 0.980 | 0.040 | 0.127 | ✅ |
| **all** | **≥0.99** | **~0.94** | **~0.03** | **~0.15** | **5/5** |

Held-out addressing means (E1): unseen-identity 0.995 · paraphrase 0.969 · hard-names 0.999 ·
same-entity/diff-attr 0.996 · recombined 0.995 · stable 0.997. No-match false-accept 0.152, false-reject
0.055, recall 0.848. **Worst-seed G1 = 0.987; mean E1-over-B0 improvement = 0.909.** B0 (anonymous
slots) at chance on every split.

## Primary measurements (summary)
- E1 e2e (G1) ~0.94; B0 e2e ~0.03.
- Correct-key top-1 by split: 0.97–1.00 (above the frozen 0.80/0.75 bars on all).
- No-match false-accept 0.152 (≤0.30), false-reject 0.055 (≤0.15), recall 0.848 (≥0.70).
- Worst-seed G1 0.987 (≥0.70 floor); 5/5 seeds pass all gates (required 4/5).
- Deterministic replay: byte-identical. Leakage/shortcut: all_pass.

## Interpretation (bounded)
Confirms **only** that the frozen E1 explicit-key dual-encoder bundle reproduces reliable semantic
episode-local key matching with hard top-1 retrieval — beating the frozen anonymous BindingSlots
baseline — on an **independent** vocabulary, templates, evaluator, and seeds at comparable density. It
does **not** attribute the effect to any component, repair anonymous BindingSlots, establish arbitrary
capacity / versioning / production readiness / long-context / external-table replacement, or unblock
KDA. `E1_FOLLOW_ON_RESEARCH_ELIGIBLE` marks eligibility for further study only. See `LIMITATIONS.md`.
