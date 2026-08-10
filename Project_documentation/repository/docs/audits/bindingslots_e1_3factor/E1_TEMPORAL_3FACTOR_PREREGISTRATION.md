# E1 latest-state three-factor factorial — preregistration (DRAFT)

**DRAFT PREREGISTRATION — for approval. Nothing here is executed.** No implementation code, no training,
no evaluation, no seed allocation. This document specifies one three-factor factorial experiment targeting
the diagnosed components of the T4 latest-state shortfall. Always preserves, in any later experiment:
`E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`KDA_VALIDATION_BLOCKED`. **T5 predecessor/successor reasoning is explicitly outside this experiment.**

## 1. Grounding (merged evidence)
The temporal transfer verdict is `E1_TEMPORAL_TRANSFER_PARTIAL` (PR #1354): the frozen C1 mechanism
transfers for identity- and position-indexed retrieval but misses the latest-state gate (T4). The
zero-training counterfactual diagnostics (PR #1356) attributed the T4 shortfall mechanically to
**`T4_SHORTFALL_MIXED`**: over-abstention **~46%**, entity-retrieval degradation under the predicate
**~22%**, within-entity latest ranking **~32%**, with the **value/read path clean (D4 = 100%)** and a
**strong abstention×entity interaction** (D2, correct-entity but null-allowed, recovered only 1.4%; D3,
correct-entity + null-suppressed, recovered 68%). The oracle arms (D1–D5) quantified ceilings **only**;
they are **not** the implementation.

## 2. Scientific question
Do **learnable, non-oracle** improvements to the three diagnosed sub-mechanisms — (F1) null/abstention
gating, (F2) latest-query entity retrieval, (F3) within-entity temporal ranking — recover the T4
latest-state shortfall, **individually and in combination**, at **comparable scale** (no capacity
increase used to explain a gain)? The factorial design is chosen deliberately because the diagnostics
proved the factors **interact** (F1×F2), so isolated one-at-a-time arms would mislead.

## 3. What is fixed vs. changed
- **Fixed:** the temporal task family, its committed vocabulary/generator semantics, ~32 keys/episode,
  the frozen-E1 reference (D0 / cell 000), the value/read path (shown clean), determinism contract
  (CPU fp32, `threads=4`), and the leakage/shortcut suite.
- **Changed (each factor a minimal, learnable inductive bias — NOT an oracle, NOT the external table):**
  - **F1 — null gating:** a learnable abstain-vs-answer mechanism (candidate: a calibrated null/margin
    gate learned on non-reserved fixtures, or a learned confidence head) that reduces over-abstention
    without fabricating answers. Must never use ground-truth match/answer at inference.
  - **F2 — latest-query entity retrieval:** predicate-conditioned encoding that prevents the "latest"
    token from diluting entity matching (candidate: separate predicate and entity sub-representations, or
    an auxiliary entity-identification signal). Must not use evaluator entity identity at inference.
  - **F3 — within-entity temporal ranking:** an order-aware scoring that uses the (already legitimate)
    position token to prefer the latest record among same-entity candidates (candidate: a learned monotone
    position bias or a small same-entity pairwise ranking term). Must not use ground-truth latest index or
    episode metadata at inference.
- **Capacity discipline:** factors are implemented with **minimal added parameters** and the **frozen C1
  training budget** (steps/lr/optimizer) held fixed where possible, so a gain is attributable to the
  *mechanism*, not to more capacity/compute. Any factor that cannot be expressed without a capacity/budget
  increase must declare it explicitly (`APPROVAL_REQUIRED_BEFORE_EXECUTION`); a confounded factor is not run
  as a clean mechanism test.

## 4. Factorial design (individual + combinations, one shared cohort)
Full **2³ = 8 cells** over the same fresh evaluation episodes: `000` (frozen-E1 reference) · `100` (F1) ·
`010` (F2) · `001` (F3) · `110` (F1+F2) · `101` (F1+F3) · `011` (F2+F3) · `111` (all three). All cells
train under the frozen recipe on identical training data and are evaluated on **one shared fresh reserved
cohort** (identical episodes across cells) so that **main effects and interaction effects** are estimable.
The reported analysis includes per-factor main effects, all pairwise interactions (with **F1×F2**
pre-flagged as the key interaction), and the three-way term.

## 5. Cohort, seeds, arms
- **Fresh seeds** disjoint from every prior seed in the program (V100 28–32; E1 dev 500–502; burned
  2028–2032; E1 final 3140–3144; confirmation 71/700–702/5140–5144; temporal 73/720–722/6140–6144).
  Proposed (pending approval): train-episode seed 91; dev 760–762; final 7140–7144.
- **Reference arm** = frozen E1 (cell 000), byte-identical to the committed frozen recipe on the new
  cohort's non-reserved fixtures where applicable.
- Same ~32-key density, same held-out splits (T1–T9) as the temporal experiment, evaluated for every cell.

## 6. Metrics
Primary (per cell, per seed, overall): **T4 latest-state** correct-key top-1 and end-to-end accuracy;
improvement over cell 000. Factorial: main effect of each factor, all interactions, on T4. Regression
guards (each cell): T1/T2/T3/T6/T7/T9 addressing (no material regression from PR #1354), no-match FA/FR
(inherited ceilings), value accuracy. Diagnostics: abstention rate, correct-entity rate, within-entity
latest rate (mirroring D0–D3 as *learned*, non-oracle measurements). T5 reported for completeness only,
**excluded** from every gate and from the conclusion.

## 7. Gates (structure frozen; numbers on non-reserved fixtures before the cohort)
- **Primary recovery:** each qualifying cell must materially exceed cell 000 on T4 by a preregistered
  margin, and the best cell must reach a preregistered absolute T4 bar — values
  `APPROVAL_REQUIRED_BEFORE_EXECUTION` (set on dev fixtures, B0/effect-size-justified, not tuned on
  reserved).
- **No-regression:** no cell may materially regress T1–T3/T6–T7/T9 or the no-match ceilings.
- **No capacity confound:** if a winning cell required a declared capacity/budget increase, the result is
  labelled capacity-confounded and cannot be reported as a clean mechanism effect.
- **Fresh-seed reliability, determinism, leakage/shortcut, no oracle at inference** — all required, same
  discipline as prior phases; ≥4/5 seeds; worst-seed floor. Numbers `APPROVAL_REQUIRED_BEFORE_EXECUTION`.

## 8. Leakage / integrity (reused + extended)
The temporal leakage suite (no status/answer in keys or queries, no exact identifier overlap, disjoint
pools, unseen eval identities, lexical + global-latest heuristic at chance, no external-table import),
**plus** an explicit **no-oracle-at-inference** proof for each factor: F1 must not read the
match/answer; F2 must not read evaluator entity identity; F3 must not read the ground-truth latest index
or episode metadata. Any oracle dependence → `PROTOCOL_VIOLATED`.

## 9. Proposed verdict vocabulary (mechanical; not a transfer validation)
`THREE_FACTOR_T4_RECOVERED_BY_<cells>` (which minimal cell(s) clear the primary recovery) ·
`THREE_FACTOR_T4_PARTIAL` · `THREE_FACTOR_T4_NOT_RECOVERED` · `THREE_FACTOR_CAPACITY_CONFOUNDED` ·
`THREE_FACTOR_PROTOCOL_VIOLATED` · `THREE_FACTOR_INCONCLUSIVE` · `THREE_FACTOR_RESOURCE_BLOCKED`. Always
co-emit `E1_TEMPORAL_TRANSFER_PARTIAL`, `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`KDA_VALIDATION_BLOCKED`. A recovery emits at most `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`; it does **not**
validate transfer and does **not** unblock KDA. Never emit `E1_TEMPORAL_TRANSFER_VALIDATED` or
`E1_STRUCTURAL_TRANSFER_CONFIRMED`.

## 10. Interpretation boundaries
A recovery supports **only**: "learnable improvements to null-gating / entity-retrieval /
latest-ranking (individually or combined) recover the T4 latest-state shortfall at the preregistered
scale on the temporal family." It does **not** establish full temporal transfer, capacity independence
beyond the declared budget, T5 relational reasoning, natural-language transfer, production readiness, or
KDA readiness. A non-recovery supports only that these minimal learnable factors did not recover T4
within the bounded experiment; the external-table reliability path is unaffected either way.

## 11. Determinism, compute, futility
Determinism prerequisite (byte-identical replay on a non-reserved fixture) before any reserved cell.
Bounded compute (8 cells × fresh seeds, frozen budget; CPU fp32, `threads=4`); mechanical futility;
no selective seed restarts; no post-evaluation tuning; protocol lock committed before the first reserved
cell.

## 12. Unresolved decisions requiring approval before execution
1. **Exact learnable implementation of each factor** (F1 gate form; F2 predicate-conditioning form; F3
   order-aware form) — and confirmation each is **minimal-parameter / non-oracle**;
   `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
2. **Whether any factor requires a capacity/budget increase** (if so, it is a confounded arm, not a clean
   mechanism test) — `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
3. **All numeric gates** (primary recovery margin + absolute T4 bar, no-regression tolerances, no-match
   ceilings, fresh-seed proportion, worst-seed floor), frozen on dev fixtures.
4. **Final seed set and compute budget** (proposed in §5).
5. **Whether to run the full 8-cell factorial or a reduced fraction** in the first pass (full factorial
   recommended to estimate the F1×F2 interaction the diagnostics flagged).

Until these are approved and frozen on non-reserved fixtures, **no execution begins.** This draft
proposes the design, factorial structure, gate scaffold, integrity requirements, and open decisions only.
