# D0_PRIME_1_MATH_EXPLANATION — why the specificity test came back NOT SPECIFIC

> **Mathematical analysis of the D₀′.1 negative result. No implementation, no new experiments,
> no new metrics, no Stage A modification, no roadmap change, no new hypothesis.** Structural
> only; no semantic claim. Lie-algebraic facts below were verified numerically against the frozen
> generators (analysis, not a new structural experiment); the arguments are the deliverable.

## 0. Setup (frozen construction)
`d = 4`. Fixed skew generators `G_A=J⊗I₂, G_B=I₂⊗J, G_C=J⊗Z, G_D=X⊗J ∈ so(4)`. Feature matrix
`F ∈ ℝ^{n×4}` (rows `f_σ`, entries in `[-1,1]`). Operators
`M_σ = exp(A_σ)`, `A_σ = Σ_j f_{σ,j} G_j ∈ 𝔤₀ := span{G_A,…,G_D} ⊆ so(4)`, `s₀ = e₁`.

**Two facts about the generators (verified):**
- `dim 𝔤₀ = span{G_j} = 4` — the generators are independent, so the feature chart is a linear
  coordinate system on a **fixed 4-dimensional subspace** `𝔤₀`.
- `dim Lie⟨G_j⟩ = 6 = so(4)` — the bracket-closure of the generators is the **whole** of `so(4)`.
  Under `so(4) ≅ su(2)₊ ⊕ su(2)₋`: `{G_B,G_C}` lie in a **2-plane of su(2)₊** (axes ê₁,ê₂; ê₃
  absent) and `{G_A,G_D}` in a **2-plane of su(2)₋** (axes ê₂,ê₃; ê₁ absent).

`so(4)` acts **irreducibly** on `ℝ⁴` (over ℂ, `ℝ⁴⊗ℂ` is the `(½,½)` irrep — absolutely
irreducible).

---

## 1. Which structural quantities depend ONLY on the generators (any F)?

**Common invariant subspaces are generator-determined.** A subspace `V` is invariant under all
`M_σ = exp(A_σ)` iff invariant under all `A_σ`, iff invariant under `span{A_σ}`. For any `F` with
`span{A_σ} = 𝔤₀` (i.e. `rank F = 4`; generic, and the case for Stage A and every null), invariance
under `𝔤₀` forces invariance under the bracket-closure `Lie⟨𝔤₀⟩ = so(4)`. Since `so(4)` is
irreducible, the only common invariant subspaces are `{0}` and `ℝ⁴`. Hence:

- **Generated associative algebra dimension = d² = 16.** By **Burnside's theorem** (a subalgebra
  of `M_d(ℂ)` acting absolutely irreducibly is all of `M_d(ℂ)`), the associative algebra generated
  by an irreducible `{M_σ}` is `M_4(ℝ)`, dimension 16. *Depends only on the generators* (via
  irreducibility), for every `rank-4` `F`. ∎
- **Reachability rank = 4.** The reachable space `span{M_w s₀}` is the smallest `M_σ`-invariant
  subspace containing `s₀`; by irreducibility it is all of `ℝ⁴` for any `s₀ ≠ 0`. *Generator-
  determined.* ∎
- **Order-separation ≈ 1 and near-commuting pairs = 0.** `[M_a,M_b]=0` ⇒ (generically)
  `[A_a,A_b]=0`; but `[A_a,A_b] = Σ_{j,k} f_{a,j} f_{b,k}[G_j,G_k]` and the generators have nonzero
  brackets (they generate non-abelian `so(4)`), so `[A_a,A_b] ≠ 0` for all but a measure-zero set
  of `(f_a,f_b)`. Order changes the product for almost all words. *Generator-determined* (generic).
- **Length-3 trace symmetry `tr(M_aM_bM_c) = tr(M_aM_cM_b)` (⇒ `trace_order_frac = 0`).**
  *Proof.* `su(2)₊` and `su(2)₋` commute, so `A_σ = A_σ⁺ + A_σ⁻` gives, in the `(2,2)` rep,
  `M_σ = U_σ⁺ ⊗ U_σ⁻` with `U_σ^± = exp(A_σ^±) ∈ SU(2)`. Thus
  `tr(M_aM_bM_c) = tr(U_a⁺U_b⁺U_c⁺)·tr(U_a⁻U_b⁻U_c⁻)`. Identify `SU(2)` with unit quaternions,
  `tr(U)=2 Re(q)`. The generators force `A_σ⁺` into the **2-plane span{i,j}** (ê₃=k absent) ⇒
  every `q_σ⁺ ∈ span{1,i,j}` (zero k-part); likewise `q_σ⁻ ∈ span{1,j,k}` (zero i-part). For
  `q_b,q_c ∈ span{1,i,j}`, the quaternion commutator `q_bq_c − q_cq_b = 2(v_b×v_c)` lies along the
  **missing axis k**, and for any `q_a ∈ span{1,i,j}`, `Re(q_a·k)=0`. Hence
  `tr(U_a⁺U_b⁺U_c⁺) − tr(U_a⁺U_c⁺U_b⁺) = 2 Re(q_a⁺[q_b⁺,q_c⁺]) = 0`; identically for the `−`
  factor (commutator along the missing axis i, `Re(q·i)=0`). Both factors are `b↔c`-symmetric, so
  their product is. ∎ *Depends only on the generators' 2-plane placement, for every F.*
  (Verified: `max|tr(abc)−tr(acb)| = 2·10⁻¹⁴` for `A∈𝔤₀` vs `6.55` for full `so(4)`.)

So **`algebra_dim`, `reachability_rank`, `trace_order_frac`, `order_separation`, `n_near_commuting`
are functions of the fixed generators alone** (on the generic, full-measure set of `F`).

---

## 2. Which quantities genuinely depend on F? Where does the chart enter?
`F` enters at exactly one place: the linear coordinates of `A_σ` **inside the fixed 4-plane `𝔤₀`**
(`A_σ = Σ_j f_{σ,j}G_j`). It does **not** change which subalgebra is generated, irreducibility,
or any of the §1 invariants. It moves `M_σ` *within* `exp(𝔤₀)`. The genuinely `F`-dependent
statistics are the **magnitudes**:
- normalized commutator norms (`commutator_max/median/min`),
- abelianity off-diagonal defect (`max/mean`).
These are smooth, non-constant functions of `F` — and indeed in D₀′.1 they were the *only*
statistics with nonzero null spread. They showed Stage A at a high tail versus some nulls but
typical versus others, with no value surviving Bonferroni correction.

---

## 3. Can the invariants stay unchanged for almost any sufficiently rich F? Yes.
`algebra_dim=16`, `reachability=4`, `trace_order_frac=0`, `order_separation≈1`, `n_near=0` are the
**generic values** on the **Zariski-open, full-measure** set `{F : rank F = 4}` (the §1 proofs use
only `span{A_σ}=𝔤₀` and genericity of pairwise non-commutation). The complementary set — rank-
deficient `F`, or `F` placing all `A_σ` in a common maximal torus (simultaneously commuting) — is
measure zero. Hence for *almost any* feature chart these five invariants take identical values.
This is precisely why five different null ensembles (permute / independent / norm-preserving /
cosine-preserving / max-entropy) reproduced them exactly.

---

## 4. Character of the map `F ↦ {M_σ}`
- `F ↦ {A_σ}` is **linear and injective** (the `G_j` are independent): `ℝ^{n×4} ≅ 𝔤₀^{n}`.
- `A_σ ↦ M_σ = exp(A_σ)` is a **local diffeomorphism near 0** (locally injective / locally stable)
  but **globally many-to-one** (`exp` on the compact group `SO(4)` is periodic along torus
  directions).
- **Not structurally universal at the operator level:** the image is confined to `exp(𝔤₀)`, a
  4-parameter-per-unit subset of `SO(4)`; `M_σ` cannot be an arbitrary rotation.
- **Universal at the generated-algebra level:** for generic `F` the *associative algebra* is all of
  `M_4(ℝ)` (§1).
- **Approximately universal on the chosen invariants:** the map `F ↦ (D₀′ gauge-invariants)` is
  **generically constant** for the five §1 quantities and only weakly variable for the magnitude
  quantities (§2).

Summary: `F ↦ {A_σ}` injective-linear; `A_σ ↦ M_σ` locally injective, globally many-to-one;
`F ↦ (structural invariants)` generically constant (approximately universal).

---

## 5. Interpretation of D₀′.1

**Verdict: D (a combination), dominated by C and B; only weak, secondary bearing on A.**

- **C — inevitable consequence of the Lie-group parameterization (primary).** Because `𝔤₀`
  generates the irreducible `so(4)` and sits as fixed 2-planes inside `su(2)₊⊕su(2)₋`, the headline
  invariants (`algebra_dim`, `reachability`, `trace_order`, `order_separation`, `n_near`) are
  *theorems about the generators*, constant on a full-measure set of feature charts. They
  **cannot** discriminate `F` — by construction, not by accident.
- **B — limitation of the chosen invariants (primary).** D₀′ selected exactly those gauge-
  invariant quantities that are generator-determined; they are mathematically **blind** to the
  feature chart. The few `F`-sensitive statistics (commutator/defect magnitudes) carried the only
  discriminating power, and it was weak and inconsistent.
- **A — falsification of the feature ontology (weak / not established).** D₀′.1 does **not** show
  the feature ontology carries no information. It shows the chosen *structural invariants* are
  feature-blind, and that the *F*-sensitive magnitudes show no significant specificity. A genuine
  test of the ontology's content needs `F`-sensitive (not generator-locked) quantities and,
  ultimately, the semantic observable `Y` — which is data-blocked.

**Correction to the prior D₀′.1 framing.** The earlier summary called the result "a structural
falsification of the specificity of the current feature construction." That is too strong. The
precise statement is: *the gauge-invariant operator-algebra statistics used are generator-
determined, hence structurally incapable of testing feature specificity; the residual feature-
sensitive statistics showed no significant specificity.* The non-commutative structure reported by
D₀′ is a property of the fixed generators (irreducible `so(4)`), not evidence for or against the
feature ontology.

---

## 6. Consequence (no new experiments proposed)
Further structural experiments built on the same gauge-invariant operator-algebra statistics are
**not worthwhile**: §1 proves they are constant across feature charts by construction. Any
informative structural test would have to target the **`F`-sensitive** quantities (magnitudes),
and even those bear only on the feature chart's *geometry*, not its *semantic content* — which
remains the data-blocked question. This explanation closes the structural-specificity line on a
mathematical basis; it makes no claim about Symbol-U semantics.

> structure, not validated meaning.
