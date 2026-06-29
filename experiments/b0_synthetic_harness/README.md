# experiments/b0_synthetic_harness — B.0 Synthetic Harness Calibration

> **Scope — SYNTHETIC INSTRUMENT CALIBRATION ONLY.** Measures whether the planned
> probe / baseline / ⊥ machinery can (a) **detect planted order signal** and (b) **return null**
> on planted-null/noise data, with measured power / false-positive characteristics.
> **No external data · no semantic `Y` · no L2 `F` · no decoder · no real-world result · no
> PASS/FAIL/⊥ for Symbol-U.** A′ remains canonically halted; D₀′ remains structural-only.
> **structure, not validated meaning.**

## Why this exists
Per `SYMBOL_U_UNBLOCKED_RESEARCH_PLAN.md`, a validation result is uninterpretable until the
instrument's power and false-positive rate are known. This harness calibrates that instrument on
**synthetic** data with known ground truth — no Symbol-U data, no meaning, no inference about the
theory. It is the decoupled, self-contained B.0 track; it does **not** start real B–G.

## Design
A single parametric generator produces `y = confound·z(bag) + effect·z(order) + noise·z(gauss)`:
- **bag** depends only on unordered unit **counts** (order-blind);
- **order** is, by default, an **antisymmetric bigram** effect (`A = B − Bᵀ`): purely
  order-dependent and **invisible to the bag baseline in expectation** (`E[order|counts]=0`), yet
  linearly representable by the order-aware probe;
- ground-truth "order present" `== (effect ≠ 0)`.
Regimes (null/bag, order, weak, confounded, pure-noise) are points in `(confound, effect, noise)`.
A `order_kind="product"` option plants the full non-commutative operator product as a **hard,
probe-mismatched** order signal.

Probe = ridge out-of-fold R². Order statistic = incremental ΔR² of `[bag+bigram]` over `[bag]`,
judged against a **within-sequence shuffle null** (preserves counts, destroys order). Decision
(pre-registered: `ΔR² > null-p95` and `ΔR² > 0.01`) returns one of
`DETECTED_PLANTED_SIGNAL / CORRECT_NULL / FALSE_POSITIVE / FALSE_NEGATIVE / AMBIGUOUS`
(AMBIGUOUS = order present but nothing learnable → underpowered, not blamed on the probe).
A relabel/unit-permutation check confirms the linear probe is permutation-invariant.

## Files
- `generators.py` — parametric synthetic generator + named regimes.
- `harness.py` — featurizers, ridge OOF R², shuffle null, relabel check, decision rule.
- `test_harness.py` — control tests. Run: `python3 experiments/b0_synthetic_harness/test_harness.py`.
- `run_b0.py` — calibration sweep; writes the report. Run: `python3 experiments/b0_synthetic_harness/run_b0.py`.
- `B0_RESULT.md` — **measured report from actual execution**.

## Measured calibration (see `B0_RESULT.md`)
- **Confusion:** null/bag & pure-noise → all `CORRECT_NULL`; order(effect=1) → all `DETECTED`;
  weak(0.2) → `AMBIGUOUS` (underpowered); confounded → partial detection.
- **Operating point:** TPR = 1.00, FNR = 0.00, FPR = 0.00 (≤ designed 0.05) at effect=0.5.
- **Minimum detectable effect:** ≈ **0.50** (detection rate ≥ 0.80) at N=300, noise=1.
- **Sample size (effect=0.3):** detection 0.05 → 1.00 across N = 100 → 800 (power curve).
- **Noise (effect=0.5):** detection 1.00 at σ ≤ 1, → 0.00 at σ ≥ 2.
- **Confounding (effect=0.4):** detection 0.75 → 0.00 as bag-confound 0 → 4 (order masked).
- **Power limit (hard case):** the full non-commutative **product** signal is detected only ≈0.05
  by the linear bigram probe — it cannot linearly represent an ordered operator product.

## B.0.1 — operator-aware probe (lifts the product-signal power limit)
B.0 found a linear bigram probe under-detects pure non-commutative **product** signal (~0.05).
B.0.1 adds an **Option-A operator-product probe**: given a candidate operator family `{M_i}` and
init `s0` (as the real probe would be handed the theory's operators), the per-sequence feature is
the ordered-product state `s(seq)=M_{x_L}…M_{x_1} s0`. Files:
- `harness_operator.py` — operator-product features, mismatched-family generator, generic
  `detect_with(order_feature_fn)` (same shuffle-null machinery, so all probes compare fairly).
- `test_operator_probe.py` — control tests (run: `python3 .../test_operator_probe.py`).
- `run_b0_1.py` — operator-aware calibration sweep → `B0_1_RESULT.md` (measured).
- `generators.generate_with_assets` — exposes the generative `{M_i}, s0` to the probe.

**Measured (see `B0_1_RESULT.md`):** on the hard product signal (effect=1, noise=1), detection
rate is **bag 0.00 · bigram 0.05 · operator-matched 1.00 (median ΔR² 0.51) · operator-mismatched
0.15**. FPR ≤ 0.05; **MDE ≈ 0.30** (operator-matched); robust to noise (1.00 to σ=2, 0.85 at σ=4)
and confounding (1.00 across confound 0→4, since product features are bag-orthogonal); shuffling
order destroys detection (ΔR² 0.55 → not-detected). **Identifiability nuance:** the *mismatched*
operator family is weak (0.15) — an operator-aware probe needs approximately-correct operators;
operator-awareness alone is insufficient.

Connection to D₀′ (no claim, just a flag): the frozen Stage A operators are genuine
non-commutative **product** structure, so a future order/representation probe must be operator-
aware (linear bigram under-powers it) **and** approximately operator-correct. Instrument-design
guidance only; **no semantic implication**.

## B.0.2 — operator mismatch / identifiability calibration
Quantifies how operator-product probe power depends on the match between the true generative
family `{M_i}` and the probe family `{N_i}`. Files:
- `harness_mismatch.py` — probe-family builders: exact, gauge (`N=S M Sᵀ`, `s0'=S s0`),
  perturb(ε) (`polar(M+ε·noise)`, det-sign preserving), random, abelian (commuting diagonal),
  partial corruption(frac).
- `test_mismatch.py` — control tests (run: `python3 .../test_mismatch.py`).
- `run_b0_2.py` — mismatch sweep → `B0_2_RESULT.md` (measured).

**Measured (see `B0_2_RESULT.md`, product signal):** detect rate — exact **1.00**, gauge **1.00**
(features = `S·(true features)`, an invertible linear map → linear probe is gauge-invariant),
perturb ε=0.2 **1.00**, random **0.00**, abelian **0.00**, bag/bigram **0.00**. Perturbation power
holds to ε≈0.4 then collapses (**threshold ε≈0.8**); partial corruption tolerated to ~20% then
collapses (**threshold ≈0.4 fraction**). Abelian probe operators cannot detect non-commutative
product signal (their ordered product is count-only). This quantifies the B.0.1 caveat: the
operator-aware probe needs **approximately-correct, non-abelian** operators. Instrument-design
finding only; **no semantic implication**.

## Hard boundaries
Synthetic calibration only · no external data · no semantic `Y` · no `F`/decoder · no A′ · no real
B–G · no Symbol-U PASS/FAIL/⊥ · Stage A (`symbolu_neural/structural_v1/`) untouched · ⊥ preserved.
