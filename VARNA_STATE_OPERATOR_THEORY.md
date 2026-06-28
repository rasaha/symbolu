# Varṇa State-Operator (VSO) Theory — Minimal Specification

> **Type:** theory specification. No code, no implementation, no experiments. This document
> defines the **minimal mathematical object** that would make Symbol-U a falsifiable
> scientific theory. It does **not** assert that the theory is true, validated, or supported.
> Companions: `THEORY_FORMALIZATION.md`, `FALSIFICATION_STRATEGY.md`, `SCIENTIFIC_ROADMAP.md`.

## Core idea (stated once, plainly)

A varṇa is modeled not as a vector but as a **state-operator**: it has an intrinsic state,
but its meaning appears through **how it acts on the reading state** when composed with other
varṇas. Composition is the **ordered product of operators**, which is non-commutative by
construction — and that non-commutativity is the entire distinctive content of the theory.

---

## 1. Primitive objects

- **Finite varṇa inventory** `Σ = {σ₁, …, σₙ}`, `n = |Σ| < ∞`.
- **Reading state space** `Sᵣ = ℝ^d` for a fixed finite `d` (the *dimension* — a pre-committed
  constant, see §6).
- **Neutral initial reading state** `s₀ ∈ Sᵣ` (the reading of the empty utterance), fixed.
- **Varṇa State-Operator (VSO)** for each `σ`:
  `Ωσ = (Vσ, Mσ)` where
  - **operator component** `Mσ ∈ ℝ^{d×d}` — how the varṇa *transforms* the reading state;
  - **intrinsic state component** `Vσ := Mσ s₀ ∈ Sᵣ` — what the varṇa *is in isolation*
    (its action on the neutral state). `Vσ` is derived from `Mσ`, not independent.
- **Observable maps** `O = {O₁, …, O_p}`, each `O_i : Sᵣ → ℝ` (taken linear: `O_i(s) = u_iᵀ s`
  for fixed `u_i ∈ ℝ^d`), plus per-varṇa projections `φ_• : Ωσ ↦ ℝ^·` (§4).

The object the theory must ultimately supply is the tuple `(d, s₀, {Mσ}_{σ∈Σ}, {u_i})`.

## 2. Composition law

For an utterance `w = σ₁ σ₂ … σ_m ∈ Σ*`:

> **ρ\*(σ₁ … σ_m) = Mσ₁ Mσ₂ ⋯ Mσ_m · s₀ ∈ Sᵣ.**

Observables of the utterance are `O_i(ρ*(w)) = u_iᵀ Mσ₁ ⋯ Mσ_m s₀`. (Application order:
the product is read in sequence order; whether σ₁ or σ_m acts on `s₀` first is a fixed
convention — order-sensitivity holds either way.)

**Required properties, all satisfied by the matrix product:**
- **order-sensitive / non-commutative:** matrices generally do not commute;
- **non-additive:** `ρ*(σσ′) ≠ Vσ + Vσ′` in general;
- **finite:** `n` operators of size `d×d`, `n·d²` parameters total;
- **falsifiable & testable:** the induced sequence→observable map is a *rational series*,
  with a complete identifiability theory (§3, §6).

**Why `M_{ka} M_{ma} ≠ M_{ma} M_{ka}` is the central point.** A *bag-of-varṇas* model makes
the reading a function of the **multiset** of varṇas — formally it factors through the free
**commutative** monoid `ℕ^Σ` (the counts of each varṇa), so `ka·ma` and `ma·ka` are
identical. The VSO law makes the reading the **ordered product** of operators; because matrix
multiplication is non-commutative, `ka·ma` and `ma·ka` generically yield **different reading
states and different observables**. Non-commutativity *is* the mathematical statement that
"composition/order carries meaning." If the operators commute, the theory collapses back to a
bag (§3), and has no content beyond additive sound symbolism.

## 3. Emergence (defined, not invoked)

Let `C₀` be the **additive/abelian reference class**: models whose observable behavior factors
through `ℕ^Σ` (equivalently, realizations by *commuting* operators). Emergence is
**non-membership in `C₀`**, testable at three escalating strengths:

- **E1 — order:** `∃ a,b : O(ρ*(ab)) ≠ O(ρ*(ba))` ⟺ `Mₐ Mᵦ ≠ Mᵦ Mₐ` on the relevant subspace.
- **E2 — interaction (non-additivity):** `∃ a,b : O(ρ*(ab)) ≠ O(Vₐ) + O(Vᵦ)`.
- **E3 — class-irreducibility (the strong, decisive form):** the operators `{Mσ}` are **not
  simultaneously diagonalizable** (genuinely non-abelian); equivalently, the **Hankel matrix**
  of the series `w ↦ O(ρ*(w))` has **rank strictly greater** than that of the best abelian
  model. By Fliess–Schützenberger, the minimal `d` equals the Hankel rank; emergence is the
  statement that this rank exceeds the commutative baseline.

Emergence is therefore a **computable, falsifiable** property: fit the best abelian model;
emergence holds iff the non-commutative realization strictly out-predicts it on held-out
sequences (Hankel-rank separation). No mystical "resonance" is required to state it — though a
global-fixpoint law (a strictly larger class than the linear automaton) would be a *stronger*
emergence claim, to be earned separately.

## 4. Observables

Per-varṇa and per-utterance projections, partitioned by epistemic status:

| projection | of | status | becomes empirical via |
|---|---|---|---|
| `φ_acoustic(Ωσ)` | varṇa | **empirical** | measured spectra / formants |
| `φ_articulatory(Ωσ)` | varṇa | **empirical** | measured articulatory features |
| `φ_semantic(Ωσ)`, `O_sem(ρ*(w))` | varṇa / utterance | **empirical** | independent human semantic judgments |
| `φ_binding`, `φ_liberating` | varṇa | **theoretical** (internal coordinates) | a *bridge study* tying them to an independent binding/liberating rating |
| `φ_tension`, `φ_coherence` | utterance | **theoretical** | bridge to an independent conflict/consistency measure |
| `Ωσ`, `Sᵣ` themselves | — | **theoretical** (latent) | never measured directly |

**Empirical:** acoustic, articulatory, semantic (all require external measurement).
**Theoretical:** the internal coordinates (binding/liberating, tension/coherence) and the
state/operators — these have empirical content **only** through bridge maps. Treating the
internal binding/liberating coordinate as if it were a measured quantity is the circularity to
avoid: it is a *coordinate of the theory*, falsifiable only once bridged.

## 5. Falsification tests

The VSO theory is falsified by any of:

1. **Random-operator control:** replacing `{Mσ}` with random operators of the same `d`
   predicts the observables equally well → the specific assignment carries no information.
2. **Operators commute:** the best-fitting `{Mσ}` are (near-)simultaneously diagonalizable →
   the theory is a bag; E1–E3 fail.
3. **Additive model matches:** an additive/abelian model reproduces `O∘ρ*` on held-out
   sequences (no Hankel-rank separation) → no emergence.
4. **Relabel control:** permuting which operator is attached to which varṇa predicts equally →
   the varṇa↔operator binding is arbitrary.
5. **Cross-modal decoupling:** `φ_acoustic(Ωσ) ⟂ φ_semantic(Ωσ)` given varṇa identity → the
   "one shared state generates both channels" claim fails.
6. **Dimension blow-up:** reproducing data requires `d` to grow with corpus/utterance length →
   not a finite-state theory; vacuous.
7. **Human sound-symbolism failure:** entailed order-effects and projection values do not match
   pre-registered human judgments → the empirical bridge fails.

The two **decisive** tests are #1/#4 (no information in the specific operators) and #2/#3
(operators effectively commute ⇒ bag). #6 is the guardrail against unfalsifiability.

## 6. Minimum constraints (what keeps it falsifiable)

A latent operator model with a *free* dimension is a universal fitter and predicts nothing.
The following are **mandatory** for the VSO theory to be science rather than curve-fitting:

- **Fixed finite dimension `d`**, pre-committed (the Hankel rank target).
- **One operator `Mσ` per varṇa**, shared across **all** utterances — no per-word, per-context
  operators.
- **Fixed neutral state `s₀`** and **fixed observable maps `{u_i}`** (no refitting per item).
- **No per-word refitting** of any component.
- **No post-hoc tuning** of `d`, operators, or projections after seeing test outcomes.
- **Pre-registered predictions**, especially the sign/magnitude of permutation-pair order
  effects entailed by the (non-commuting) operators.
- **Identifiability:** `{Mσ}` recoverable up to the known gauge (a global `GL_d` change of
  basis) from observable sequence data, and **over-determined** (far fewer parameters than
  independent observable constraints).

Under these, the model is heavily over-constrained — `n` operators must reproduce the
observables of *exponentially many* utterances — which is exactly what makes it refutable.

## 7. Relation to the previous formulation

| | Old: `σ → a(σ) → F` | New: `Ωσ = (Vσ, Mσ)`, ordered product |
|---|---|---|
| primitive | symbol + external attribute lookup | varṇa as a state-operator that *acts* |
| composition | `F` of attribute values (often collapses to a bag) | non-commutative operator product (bag excluded by construction) |
| order | optional, easy to lose | intrinsic and unavoidable |
| identifiability | unspecified | complete theory (Hankel/Fliess) |
| cross-modal content | none natural | one state generates acoustic *and* semantic channels |

**What improves:** faithfulness to "intrinsic ontological unit that participates in
interaction"; non-commutativity is built in, not bolted on; identifiability and emergence
become *computable*; a genuinely new testable claim (cross-modal coupling) appears.

**What risk increases:** the operator/state is **latent**. A free latent dimension makes the
model unfalsifiable (universal approximation). The burden therefore **shifts** from "specify
`a`" to "**bound and fix `Sᵣ` (the constraints of §6)**." The new formulation is *more*
falsifiable **only** under those constraints, and *less* falsifiable without them. This
trade-off is the central caveat of adopting VSO.

## 8. Relation to Sanskrit (analyzed, not assumed)

- **Mathematically essential:** **No.** The operator-product/automaton structure is
  alphabet-agnostic; `Σ` may be any finite inventory.
- **Historically discovered coordinate system:** **The charitable, defensible reading** — *if*
  a privilege claim is made and tested (below).
- **One privileged basis:** a *non-trivial empirical* claim that would make Sanskrit
  scientifically load-bearing: that the varṇa inventory is a privileged coordinatization of
  `Sᵣ` — e.g., minimal `d`, or it makes `{Mσ}` block-diagonal/sparser than arbitrary
  inventories, or it is universal across languages. The strongest such version: the varṇa
  categories are the **irreducible representations of a symmetry group of the articulatory
  manifold**, so the inventory is *forced, not chosen*. This is a conjecture to state and test,
  not an assumption.
- **Naming / gauge:** the fallback if no privilege exists — then "varṇa" is a label and the
  basis is one of many.

**Conclusion:** Sanskrit is **not** mathematically essential; it is **at most** a candidate
privileged coordinate system (an open empirical question) and **at least** a naming/gauge
layer. The theory's mathematical interest rests on the non-commutative operator structure, not
on the inventory's cultural identity.

## 9. Open questions (what remains undefined)

- **Dimension `d`** — unknown; must be pre-committed (Hankel-rank target).
- **Operator entries `{Mσ}`** — entirely unspecified; the core empty slot.
- **Observable maps** `{u_i}`, `φ_•` — functional forms and parameters undefined.
- **Neutral state `s₀`** — unspecified (gauge-fixable).
- **Whether the Sanskrit basis is privileged** — open empirical conjecture (§8).
- **How VSO connects to CSR** — CSR (contextual semantic resonance) is plausibly the
  *global/fixpoint* extension of the local operator product (the larger class in §3); the exact
  relation is undefined and would be a strictly stronger theory.
- **How to empirically estimate `{Mσ}`** — in principle via Hankel-matrix spectral methods on
  observable sequence data, but the estimation procedure, identifiability conditions, and
  required data are unspecified.

## 10. Final verdict

1. **Does VSO make Symbol-U more mathematically coherent?** **Yes.** It gives a single,
   well-typed object (`d, s₀, {Mσ}, {u_i}`), a definite composition law, and a precise,
   computable notion of emergence — replacing an undefined "reading function" with a specific
   (if still unfilled) structure.
2. **Does it make ρ\* definable?** **It makes ρ\* definable *in form*** — `ρ* = Mσ₁⋯Mσ_m s₀` is
   a complete functional schema. It is **not yet defined in content**: the operators are
   unspecified (§9). VSO converts "ρ\* is an open research target" into "ρ\* is a known schema
   with `n·d²` unknown parameters and a known identifiability theory."
3. **Does it make the theory more falsifiable?** **Conditionally and two-edged.** *More*
   falsifiable under the §6 constraints (fixed finite `d`, one operator per varṇa, fixed maps,
   pre-registration) — it adds cross-modal and order-prediction tests the old form lacked.
   *Less* falsifiable without them (latent-variable universal fitter). Net: an improvement
   **iff** the parsimony constraints are adopted as part of the theory.
4. **Next scientific step after this document.** State the **minimal identifiable instance**:
   commit a small `d`; declare the estimation target `{Mσ}` and the projections; and write the
   **identifiability + emergence theorem** — "the minimal non-commutative realization of
   `O∘ρ*` has Hankel rank `> ` the abelian baseline, and `{Mσ}` is recoverable up to `GL_d`
   gauge from observable sequence data." That theorem (not any experiment, not any code) is the
   object whose construction or refutation determines whether Symbol-U has distinctive content.

> **Disclaimer (restated):** this document defines a *candidate minimal object only*. It does
> not claim the VSO theory is true, that any `{Mσ}` carry real structure, or that emergence
> obtains. Those are exactly the questions the object is built to make answerable.
