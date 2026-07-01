# Design Note — Primitive Vṛtti Without Polarity Coordinates

**Status:** Theory/architecture design only. No implementation, no code, no experiments, no Stage A modification, no pre-registration change. No semantic claim.

**Corrected ontology (frozen for this note):** each varṇa → one **irreducible** vṛtti; a vṛtti is a **primitive** semantic propensity with **no** internal polarity/intensity/valence coordinates; letters compose into a **bound/conditioned** state first; **polarity/assimilation is EMERGENT after composition**, never an input; not acoustic-iconic.

**Strict prohibitions honored:** no polarity/intensity/binding-liberating input coordinate; no lexicon polarity/counter-pole grounding; no gloss embeddings; no fitting operators to target meanings. Polarity appears only as a possible **emergent readout**.

---

## 0. Consequence: the grounding problem is relocated, not solved

The previous recommendation (polarity+intensity coordinates) is **withdrawn** — it decomposed the primitive, which the ontology forbids. With coordinates, lexicon-grounding, embeddings, and fitting all removed, a primitive vṛtti has **no interior and no pre-specified per-unit data.** Therefore constraint can live in only two coordinate-free places:

- **(R) relations among the primitives** (a congruence / presentation), or
- **(A) an assimilation dynamics** applied after composition.

Anything else leaves L free ⇒ unfalsifiable. This is the central finding; everything below follows from it.

## 1. What axiom is needed?

Not a coordinatization. Under the primitive ontology the missing axiom is a **structure-and-emergence axiom** with three clauses:

1. **Primitive-type axiom:** a vṛtti is an *atomic* element of a composition algebra (operator / kernel / morphism / free generator) — specified as a whole, with no coordinates.
2. **Constraint axiom (the load-bearing one):** the primitives carry a **pre-specified, coordinate-free constraint** — either relations R (a congruence on Σ*) or a pre-specified assimilation map A — since coordinates, lexicon fields, embeddings, and fitting are all excluded.
3. **Emergence axiom:** polarity/assimilation is a **functional Φ on the composed state only**, undefined on single primitives.

Without clause 2, the theory is vacuous (see §8).

## 2. Can a primitive vṛtti be modeled as … (coordinate-free)?

| candidate | coordinate-free primitive? | verdict |
|---|---|---|
| abstract symbol | yes (free generator) | **works** — but inert until a representation/relations are added |
| state | — | **no** — a state is *acted upon*; a vṛtti *acts* (Assumption 3). Type error. |
| operator | yes (atomic monoid element) | **works** |
| Markov kernel | yes (atomic stochastic map) | **works** |
| category morphism | yes (atomic arrow) | **works** (most general) |
| grammar rule | yes (production) | **works** |
| energy potential | as composition: **no** | energies **sum commutatively → order-blind**, contradicting Assumption 4. Admissible only as the *assimilation functional* A, not as the composition. |

So operators, kernels, morphisms, grammar rules, and free symbols all admit coordinate-free primitives; **states are the wrong type**; **energy belongs in the readout, not the composition.**

## 3. What structure lets primitives compose first, polarity emerge after?

A **non-commutative monoid/category with a separate readout functional**:
- composition in a non-abelian monoid/category produces the **bound/conditioned** composed element (raw meaning-state);
- an **emergent functional** Φ (a class function / character / energy-minimizer / fixed-point of a settling map) applied to the *whole* composed element yields polarity/assimilation.

Key property: the emergent quantity is a **functional of the entire composite, undefined on single generators** — exactly "bound state first, polarity after."

## 4. What replaces the polarity+intensity coordinate proposal?

An **emergent assimilation functional** `Φ∘A` on the composed state. Polarity moves from *input coordinate* to *output readout* computed after an **assimilation/settling map A**; "intensity" becomes the emergent magnitude of the composed state, not an input. The replacement is an **output map, not an input coordinate.**

## 5. Which category is the missing axiom?

**Primitive type + assimilation functional + readout** (state space also required). **Composition law is already given** (Assumption 4); **polarity is removed from the input entirely** and lives only in the readout. It is *not* a coordinate axiom.

## 6–7. Candidate axiom sets (no polarity input)

**P1 — Free-monoid representation + emergent functional (baseline).** Vṛtti = abstract generator; word = free-monoid element; L = an *unconstrained* representation ρ:Σ*→G; polarity = Φ(ρ(word)·s₀). Codomain: an operator/kernel monoid, ρ free. Det or stochastic. **Falsifiable: NO** (ρ free ⇒ any readout achievable). Rules out nothing. *Included to mark the vacuity floor: coordinate-free + no relations + no fitting = predicts nothing.*

**P2 — Presented monoid ⟨Σ | R⟩ + emergent invariant.** Vṛtti = generator of a monoid with **pre-specified coordinate-free relations R** (e.g. synonymy/collapse/commutation from the tradition); word = element of the quotient; polarity = a **class function** constant on R-classes. Codomain: the presented monoid (or a faithful representation). Det or stochastic. **Falsifiable: YES iff R is pre-specified and non-trivial** — the claim is that R-respecting invariants match observed word properties beyond relation-scrambled controls, *without per-vṛtti fitting*. Rules out representations violating R. **Requires the tradition to supply R** (relations, not coordinates).

**P3 — Primitive Markov kernels + emergent drift/entropy readout.** Vṛtti = a *whole* primitive kernel K_σ on a finite symbolic X (not built from coordinates); word = Chapman–Kolmogorov composite; polarity = emergent property of the **composed** kernel (does it drive the state toward a bound region vs disperse it — entropy change/drift of the composite, never of one K_σ). Codomain: Markov kernels. Stochastic (det = point-mass). **Falsifiable: only if the K_σ are pinned by pre-specified relations** (else the whole-kernel values are unspecified and unfittable). Rules out entropy-neutral realizations for the emergence. (Collapses into P2 for its constraint.)

**P4 — Category morphisms + functorial emergence (most general).** Vṛtti = atomic morphism in 𝒞; word = composite; L = a functor from the free category on Σ to 𝒞; polarity = a **functorial invariant** of the composite. Codomain: Hom(𝒞). Det (Vect) or stochastic (Stoch). **Falsifiable: only with relations / a constrained 𝒞** (same gap as P1). Rules out nothing without relations. General frame, not itself a constraint.

**P5 — Compose-then-Assimilate (encodes the ontology directly).** Vṛtti = a primitive operator/kernel; ordered composition yields a **bound/conditioned raw state s_raw**; a separate **assimilation map A** (a settling/relaxation: projection onto a constraint manifold, an energy-minimizer, or a fixed-point of a dynamics) produces the assimilated state; polarity = a functional of the **assimilated** state (which basin it settles into). Codomain: operators/kernels **plus a distinguished A**. Det or stochastic. **Falsifiable: iff A is pre-specified and non-trivial** (not fit). Rules out theories with no post-composition dynamics. **This set matches Assumptions 4–6 exactly** (bound state first; polarity emerges after assimilation) and localizes the new content in **A**.

## 8. Where is polarity mathematically necessary?

**Nowhere as an input.** Polarity is necessary *only* in the readout functional Φ, and *only if* the theory intends to predict observed word-level polarity. If polarity is not a prediction target, it need not appear at all. Keep it strictly out of L and the primitives; admit it only as one possible emergent Φ.

**Critical (vacuity) note.** Because coordinates, lexicon-grounding, embeddings, and fitting are all excluded, the theory is **non-vacuous only if clause-2 (relations R or assimilation A) is pre-specified.** If neither R nor A is supplied — i.e. primitives are free and nothing post-composition is fixed — then L is mathematically undetermined and the theory predicts nothing (P1). The corrected ontology therefore **forces** the real work onto **R or A**; there is no coordinate-free escape that avoids both.

## 9. Recommendation

**Primary: P5 (Compose-then-Assimilate).** It is the *only* candidate that encodes the corrected ontology's own assumptions (4–6) directly: primitives stay atomic and coordinate-free; composition produces the bound/conditioned state; **all** polarity/assimilation lives in a post-composition map A and a readout Φ. The concrete missing axiom reduces to **specifying A** (the assimilation dynamics) in a **pre-specified, coordinate-free** form — that is now the single blocker, and it is the honest successor to the (withdrawn) coordinate proposal.

**Fallback: P2 (Presented monoid).** If the tradition can supply **coordinate-free relations R** among vṛttis (equivalences/collapses/commutations), falsifiability follows from R-respecting invariants without fitting. Absent both A and R, only P1 remains — and P1 is unfalsifiable, which is the outcome to avoid.

> structure, not validated meaning.
