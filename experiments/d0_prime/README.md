# experiments/d0_prime — D₀′ Gauge-Invariant Operator-Algebra Analysis

> **Scope — STRUCTURAL / gauge / operator-algebra ONLY.** Implements and runs the D₀′ milestone
> from `SYMBOL_U_UNBLOCKED_RESEARCH_PLAN.md` on the frozen, feature-derived Stage A operators,
> reproduced **read-only** (Stage A is never modified). It produces **no semantic result**:
> no semantic `Y`, no L2 `F`, no decoder, no A′ analysis, **no PASS/FAIL/⊥ for Symbol-U
> semantics**, no inference about meaning. Self-contained — no external dataset.
> **structure, not validated meaning.**

## What it answers
A single structural question: *is the frozen Stage A operator family genuinely non-commutative
(class-irreducible), or does it effectively collapse to an abelian / bag structure?* This is the
cheapest **terminal structural falsifier** available without external data, and it supplies the
gauge-invariant observables any future operator validation (Milestone D) would reuse.

- A **nontrivial** verdict means only **"nontrivial frozen operator algebra"** — *not* semantic
  validity, and *not* validation of the operators as the "true" ones (they are a feature-derived
  benchmark proxy).
- An **abelian** verdict would be a **structural falsification of this operator instance** (the
  non-commutativity claim), nothing more.

## Files
- `operator_algebra.py` — analysis primitives + synthetic controls + pre-registered decision.
- `test_operator_algebra.py` — control-validation tests (identity & commuting-diagonal ⇒ abelian;
  random-orthogonal ⇒ nontrivial). Run: `python3 experiments/d0_prime/test_operator_algebra.py`.
- `run_d0_prime.py` — runs the analysis on the frozen operators + controls; writes the report.
  Run: `python3 experiments/d0_prime/run_d0_prime.py`.
- `D0_PRIME_RESULT.md` — **measured report generated from actual execution**.

## Measures (with gauge tags)
- **Inventory** — count, shape, Frobenius norm, rank, condition number, det, trace.
- **Pairwise non-commutativity** — `[Mₐ,M_b]`; normalized Frobenius norm (*orthogonal-invariant
  diagnostic*) and commutator **rank** (*GL-invariant*; 0 ⟺ commute); near-commuting pairs.
- **Abelianity defect** — off-diagonal mass of every operator in the eigenbasis of a generic
  combination (~0 across all ⟺ simultaneously diagonalizable ⟺ abelian).
- **Generated-algebra dimension** — `dim span{M_w : |w|≤L} ⊆ ℝ^{d×d}` (*GL-invariant*); the
  emergence/"rank-beyond-abelian" measure, bounded by `d²`, calibrated against the commuting
  control (abelian baseline) and the random control (full).
- **Trace-word order sensitivity** — `tr(M_aM_bM_c)` vs `tr(M_aM_cM_b)` (*fully GL-invariant*).
- **Reachability + order separation** — scalar-Hankel reachability rank (`≤ d`, descriptive) and
  the fraction of words whose state `M_w s₀` changes under reordering (abelian ⇒ 0).

Pre-registered thresholds (fixed before execution): `TOL_COMMUTE=1e-8`, `TOL_ABELIAN=1e-6`,
`RANK_TOL=1e-9`. Decision = **abelian** iff max commutator `< TOL_COMMUTE` **and** abelian defect
`< TOL_ABELIAN` **and** algebra dim `≤ d` **and** trace order-frac `= 0`; otherwise **nontrivial**.

## Measured outcome (see `D0_PRIME_RESULT.md`)
The frozen Stage A family (n=14, d=4, SO(4)) is **STRUCTURALLY NONTRIVIAL**: generated-algebra
dimension **16 = d²** (abelian baseline 4; separation **+12**), **0/91** near-commuting pairs,
full-rank commutators, order-separation **1.0**. It sits with the random-orthogonal control at
the fully non-abelian end and far from the abelian (identity / commuting-diagonal) controls.
**No structural falsification of the operator instance.**

**Honest caveat (witness sensitivity).** The length-3 **trace** witness reads **0** order-
sensitivity for Stage A (`max|Δtr| ≈ 1e-15`) although the family is strongly non-commuting —
i.e. order is invisible to the length-3 trace here but plainly visible in the *state*
(order-separation 1.0) and in the *generated algebra* (dim 16). The trace witness is therefore a
weaker discriminator for this family; the state-level and algebra-dimension measures are the
informative ones. Reported as measured, not engineered around.

## Hard boundaries
Structural only · no semantic `Y` · no `F`/decoder · no A′ · no B–G · no external data ·
Stage A (`symbolu_neural/structural_v1/`) untouched (operators reproduced read-only by loading
`features.py`/`operators.py` by file path; the package init, which imports torch, is bypassed).
⊥ preserved (no semantic decision emitted).
