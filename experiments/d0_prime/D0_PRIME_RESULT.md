# D0_PRIME_RESULT — Gauge-Invariant Operator-Algebra Analysis (measured)

> **STRUCTURAL / gauge / operator-algebra ONLY.** Generated from actual execution of `experiments/d0_prime/run_d0_prime.py` on the frozen, feature-derived Stage A operators (reproduced read-only; Stage A unmodified). **NOT semantic validation · NOT A′ · NOT PASS/FAIL/⊥ for Symbol-U semantics.** A nontrivial result means only *nontrivial frozen operator algebra*; an abelian result would be a structural falsification of *this operator instance* only. No semantic `Y`, no L2 `F`, no decoder, no inference about meaning.

Operator family: **n = 14** units `['p', 'b', 't', 'd', 'k', 'g', 's', 'z', 'm', 'n', 'r', 'l', 'a', 'i']`, dimension **d = 4** (SO(d)). Pre-registered thresholds: TOL_COMMUTE=1e-08, TOL_ABELIAN=1e-06.

## 1. Inventory (Stage A)
- operators: 14, shapes: [(4, 4)]
- Frobenius norm: [2.0000, 2.0000]  (√d = 2.0000 expected for orthogonal)
- rank: [4, 4]  · condition number: [1.0000, 1.0000]
- determinant: [1.0000, 1.0000]  · trace: [0.1785, 2.0420]

## 2. Cross-family comparison (Stage A vs controls)

| family | max ‖[Mₐ,M_b]‖ (norm.) | near-commuting pairs | abelian off-diag defect (max) | algebra dim (≤ d²=16) | trace order-sens. frac | order-separation frac | reach. rank (≤d) | verdict |
|---|---|---|---|---|---|---|---|---|
| Stage A (frozen, feature-derived) | 0.9752 | 0/91 | 0.9904 | 16 | 0.0000 | 1.0000 | 4/4 | nontrivial |
| control: identity | 0.0000 | 91/91 | 0.0000 | 1 | 0.0000 | 0.0000 | 1/4 | ABELIAN |
| control: commuting-diagonal | 0.0000 | 91/91 | 0.0000 | 4 | 0.0000 | 0.0000 | 1/4 | ABELIAN |
| control: random-orthogonal | 0.9531 | 0/91 | 0.9878 | 16 | 0.7885 | 1.0000 | 4/4 | nontrivial |

## 3. Stage A detail
- normalized commutator norm: min=0.1045, median=0.5794, max=0.9752
- commutator rank range: [4, 4] (0 ⟺ exactly commuting)
- near-commuting pairs (< TOL_COMMUTE): 0 of 91
- generated-algebra dimension by word length: {0: 1, 1: 9, 2: 16} (ceiling d²=16)
- abelian off-diagonal defect: mean=0.5856, max=0.9904
- trace-word order sensitivity: frac=0.0000, max |Δtr|=1.499e-15 (tr is conjugation-invariant ⇒ fully gauge-invariant witness)
- reachability (scalar Hankel) rank: 4/4; order-separation frac=1.0000

### Generated-algebra dimension vs abelian baseline
- Stage A: **16** / 16
- abelian baseline (commuting-diagonal control): 4 / 16
- full non-abelian reference (random-orthogonal control): 16 / 16
- **algebra-dimension separation above the abelian baseline: 12** (> 0 ⇒ order/non-commutativity adds realizable structure the abelian model cannot)

## 4. Structural decision (pre-registered, structural only)
> **STRUCTURALLY NONTRIVIAL non-commutative family (structure only; NOT semantic validity)**

Interpretation guard: this verdict concerns ONLY the algebraic structure of the frozen, feature-derived Stage A operator instance. It is **not** evidence about meaning, dictionary prediction, or Sanskrit privilege; it does **not** validate the operators as the 'true' ones (they are a feature-derived benchmark proxy); and it is **not** an A′/semantic PASS/FAIL/⊥. A negative (abelian) verdict would structurally falsify this instance; the measured verdict above is reported with no further semantic inference.

## 5. Sanity of controls (calibration)
- control: identity: verdict = ABELIAN, algebra dim = 1, order-sep = 0.0000
- control: commuting-diagonal: verdict = ABELIAN, algebra dim = 4, order-sep = 0.0000
- control: random-orthogonal: verdict = nontrivial, algebra dim = 16, order-sep = 1.0000

> structure, not validated meaning.
