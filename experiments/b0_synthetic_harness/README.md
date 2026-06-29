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

## Forward-looking caveat (no claim, just a flag)
The hard-case result connects to D₀′: the frozen Stage A operators are a genuine non-commutative
**product** structure, which a **linear** order probe under-detects. Any future order/representation
probe intended to capture such structure must be non-linear or operator-aware — a linear bigram
baseline would under-power it. Recorded for instrument design; **no semantic implication**.

## Hard boundaries
Synthetic calibration only · no external data · no semantic `Y` · no `F`/decoder · no A′ · no real
B–G · no Symbol-U PASS/FAIL/⊥ · Stage A (`symbolu_neural/structural_v1/`) untouched · ⊥ preserved.
