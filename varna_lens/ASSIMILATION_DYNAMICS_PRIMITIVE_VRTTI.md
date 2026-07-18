# Design Note — Coordinate-Free Assimilation Dynamics for Primitive Vṛtti Composition

**Status:** Theory/architecture design only. No implementation, no code, no experiments, no Stage A modification, no pre-registration change. No semantic claim.

**Ontology (frozen):** vṛttis are primitive and coordinate-free; ordered composition creates a bound/conditioned composite; polarity/assimilation is an **emergent readout after composition**, never input. Missing structure = the assimilation map **A** (or coordinate-free relations R).

**Strict prohibitions honored:** no polarity/intensity input coordinate; no gloss embeddings; no fitted operators; no semantic-target leakage; no reused binding/liberating coordinates.

---

## 0. Pipeline and two mandatory meta-axioms

Composition `C : Σ* → 𝒮_raw` (e.g. `C(w)=ρ(w)·s₀` or the composed element `ρ(w)`); assimilation `A : 𝒮_raw → 𝒮_assim`; readout `Φ : 𝒮_assim → 𝒪`. Meaning pipeline: `w → C → A → Φ`.

Two properties any admissible `A` must satisfy — both coordinate-free:

- **(Autonomy / no leakage)** `A` takes **no target argument**; it is a function of the composed object and the fixed algebra alone, fixed before any word is read. This is the mathematical form of "no semantic-target leakage."
- **(Order-faithfulness)** `A∘C` is **not** invariant under permutation of the word (generically). Assimilation must not erase the only nontrivial content composition produced; maps that wash out order (ergodic/stationary limits) violate this.

And one defining property: **assimilation = idempotence.** "Assimilated" means stable under further assimilation, `A∘A = A`. So `A` is a retraction/closure/projection (or the limit of a flow, idempotent on its image); `𝒮_assim = Im(A) =` the fixed-point set.

## 1–2. Domain and codomain

- **Domain of A:** the raw composite space `𝒮_raw` — the carrier state `X`, or the composition monoid `M`, or the distribution space `𝒫(X)` (kernel case).
- **Codomain of A:** either an **endomap** `𝒮_raw → 𝒮_raw` with image = the assimilated (fixed-point) set, or a **quotient** `𝒮_raw → 𝒮_raw/∼`. Both are idempotent by construction.

## 3. What kind of map is A?

Ranked by coordinate-freeness and fit to "assimilation": **quotient**, **closure operator**, **flow-to-attractor**, **projection onto invariant set**. `Normalization` and `saturation` are special/weak cases; `minimization` is admissible only with an *intrinsic* functional. The unifying property across all is **idempotence**.

## 4. Coordinate-free? 
Yes. Closure operators (extensive, monotone, idempotent — pure order theory), quotient maps and colimits (categorical), and intrinsic attractor flows are all basis-free. The only way `A` sneaks in coordinates is via a metric/energy presupposing a basis — avoided by order-theoretic or categorical definitions.

## 5. Pre-specified without fitting?
Yes — `A` can be fixed by the intrinsic structure of the composition algebra (a congruence, an invariant subspace, a stationary law, a closure system), never by targets. **But** see §Unification: *pre-specified* and *falsifiable* are not the same, and only a subclass of pre-specified `A` is falsifiable.

## 6. Emergent readout without polarity input
`Φ` reads a **structural invariant of the assimilated state** — which basin/fixed-point it settled into, which equivalence class, the support/concentration of a limit. Any "polarity" is a **post-hoc interpretation** of that invariant (e.g. calling a concentrated limit "binding"), applied after the fact, never fed in. Polarity is absent from `C`, `A`, and the primitives; it exists only as one possible `Φ`.

## 7. Existing mathematics

| construct | A as… | coordinate-free | order-faithful | notes |
|---|---|---|---|---|
| quotient maps | canonical projection to `M/∼` | yes (categorical) | iff ∼ respects order | assimilated = ∼-class |
| closure operators | order-theoretic closure `c` | yes | generically | assimilated = smallest closed superstate |
| monoid reductions | reduction to normal form | yes (rewriting) | mostly | intrinsic to composition |
| categorical colimits | coequalizer / colimit | yes (universal) | inherits diagram | most general |
| projection onto invariant subspace | spectral projection of `ρ(w)` | yes (basis-free) | **yes** | **L-dependent** (see §Unification) |
| attractor dynamics | flow to attractor | yes if intrinsic | risky | needs dissipation; **L-dependent** |
| Markov stationary distribution | map to stationary law | yes | **often violates** (washes out order) | asymptotics lose finite-order info |
| normalization flows | canonical-form flow | metric-dependent | risky | weak/coordinate-prone |
| energy minimization | argmin of intrinsic functional | only if functional intrinsic | generically | coordinate risk |

## 8–9. Candidate assimilation axioms

**A1 — Invariant-Subspace Projection.** `A(s) = P_w s`, projection onto the invariant subspace of the composed operator `ρ(w)`. *Assumes:* linear operators with spectral structure. *Rules out:* non-spectral/kernel-only primitives; degenerate cases. *Order:* preserved (`ρ(w)` order-dependent). *Falsifiable:* **NO alone** — the projection depends on the specific (free) operator values `L`. *Compatible:* yes.

**A2 — Normal-Form / Congruence Quotient.** `A =` canonical projection to `M/≈` for a **pre-specified abstract congruence** `≈` (relations R), or reduction to normal form under a confluent rewriting system. *Assumes:* R is given, coordinate-free, intrinsic to composition. *Rules out:* distinctions finer than `≈`. *Order:* preserved except where R intentionally identifies order-variants. *Falsifiable:* **YES** — the `≈`-class invariants are `L`-invariant and testable against scramble without fitting. *Compatible:* yes. **This is the R path in disguise.**

**A3 — Attractor / Relaxation Flow.** `A(s)=lim_{t→∞} φ_t(s)` for an intrinsic dissipative dynamics (e.g. Perron limit of `ρ(w)`, gradient flow of a Lyapunov functional). *Assumes:* attractors exist; convergence; **dissipation** (rules out norm-preserving/orthogonal, i.e. Stage-A-style, operators). *Rules out:* non-dissipative realizations. *Order:* at risk — must use word-dependent attractors; global fixed points destroy order. *Falsifiable:* **NO alone** — attractor depends on the free `L`. *Compatible:* kernels/contractive yes; orthogonal no.

**A4 — Closure Operator.** `A = c`, a closure on a lattice of conditioned states (`s ≤ c(s)`, monotone, idempotent) — span/convex-hull/orbit-closure/saturation. *Assumes:* an intrinsic partial order / lattice. *Rules out:* structureless states; sub-closure distinctions. *Order:* preserved if the poset is order-sensitive. *Falsifiable:* **YES if the closure system is pre-specified abstractly** (then `L`-invariant). *Compatible:* yes (fully order-theoretic).

**A5 — Categorical Colimit.** `A =` a universal construction (coequalizer/colimit) gluing the composite to a canonical object. *Assumes:* a category with the colimits + a specified diagram (= relations). *Rules out:* nothing structurally. *Order:* inherits the diagram. *Falsifiable:* **only with specified relations** (like A2/A4). *Compatible:* yes; most general, least concrete.

## Unification (the central result): a falsifiable A *is* an R

Even with `A` fixed, the primitive assignment `L` remains **free** (coordinate-free, unfitted, ungrounded). Therefore:

- **`A` that depends on the operator values** (A1 invariant-subspace, A3 attractor) inherits `L`'s arbitrariness. Its readout is `L`-dependent, so it cannot be tested without first grounding `L` — which the ontology forbids. **Elegant but unfalsifiable.**
- **`A` is falsifiable iff its readout `Φ∘A∘C` is `L`-invariant** — i.e. it depends only on the **relational structure** among words, not on which operators were chosen. The only such `A` are **quotients/closures by pre-specified abstract relations R** (A2, A4, A5). Even the "canonical" (Cayley/left-regular) representation removes `L`'s arbitrariness only by making everything a function of the presentation `⟨Σ | R⟩`.

**Conclusion:** the "specify A **or** R" fork collapses. A *falsifiable* assimilation map is a quotient/closure induced by **pre-specified relations R**; a purely dynamical/spectral `A` does **not** escape the free-`L` problem. `A` and `R` are two faces of one missing object, and the falsifiable face is `R`.

## 10. Recommendation

- **Primary: A2 (Normal-Form / Congruence Quotient), equivalently A4 (Closure).** It is the only candidate that is simultaneously coordinate-free, pre-specified-without-fitting, order-faithful, and **falsifiable** (its readout is `L`-invariant). Its concrete blocker is exactly the R blocker: **supply the abstract relations `≈` / closure system** — coordinate-free equivalences/collapses/commutations among vṛtti-composites, specified before any word is read. This is the honest, non-vacuous successor to "specify A."
- **Fallback / exploratory only: A1 or A3 (spectral projection / attractor flow).** Retain as *descriptive* devices for visualizing how conditioned states settle, but **not** as falsification instruments: their readouts are `L`-dependent and cannot be tested while `L` is free. A3 additionally requires dissipation, so it is incompatible with norm-preserving (Stage-A-style) operators.

**Net:** assimilation can be made coordinate-free and leakage-free in several ways, but only a **relational** `A` makes the primitive theory testable. The remaining work is not to invent a dynamics — it is to state, coordinate-free and in advance, the **relations** under which composites are assimilated to the same meaning.

> structure, not validated meaning.
