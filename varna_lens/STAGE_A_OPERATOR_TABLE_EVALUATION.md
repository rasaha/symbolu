# Design Note — Can Stage A Become the Canonical Varṇa Operator Table?

**Status:** Architectural evaluation only. No code written, no Stage A modification, no runs, no pre-registration change, no semantic claim. Based on a read-only inspection of `symbolu_neural/structural_v1/{operators,engine,features}.py`, `README.md`, `STAGE_A_STRUCTURAL_REPORT.md`.

**Question:** is the existing Stage A SO(4) construction the correct object to serve as the canonical operator table for the deterministic-vṛtti branch — or should a separate table be built? The mapping is *attempted-to-be-falsified*, not assumed.

---

## 1. Mathematical description of Stage A (as implemented)

| element | what Stage A actually implements |
|---|---|
| **operator family** | `M_σ = expm(Σ_j f_{σ,j} G_j)`, `d = 4`. `exp` of a skew-symmetric matrix ⇒ **M_σ ∈ SO(4)** (proper orthogonal, norm-preserving). |
| **generator basis** | **4 fixed, pre-registered skew-symmetric generators** `G_A=J⊗I, G_B=I⊗J, G_C=J⊗Z, G_D=X⊗J` on a 2⊗2 layout. `[G_A,G_B]=0` (disjoint factors commute); coupling generators do **not** commute. These span a **4-dimensional slice of the 6-dimensional Lie algebra `so(4)`** — not all of it. |
| **coordinates `f_{σ,j}`** | a **static articulatory feature chart**: `place_frontness, manner_openness, voicing, sonority_height` ∈ [−1,1]. **Phonological, hand-set, explicitly "NOT claimed to carry meaning."** |
| **inventory** | **14 toy units** (12 consonants + `a,i`) — not the varṇa set. |
| **carrier space** | `ℝ⁴` (2⊗2), fixed off-axis initial state `S0 = e₀` (normalized). |
| **composition law** | ordered matrix product `s = M_{iₙ}···M_{i₁} s₀` (`read_product`); an **order-blind additive bag** baseline (`read_bag`) is the mandatory null. |
| **readout** | the final **state vector `s ∈ ℝ⁴`**, consumed by *structure metrics* (order-effect matrix, structure score, effective rank) — **not a semantic decoder.** |
| **designed purpose** | a **structural testbed**: does a feature-grounded operator product produce inventory-specific, factorizable, order-dependent *structure* beating three nulls (bag / random-orthogonal / relabel)? Verdict on record: **FAIL** (G1–G3 pass, **G4 factorization fails**). Operators are labeled **provisional**. |

**In one line:** Stage A is an *ordered SO(4) operator product over a 14-unit toy phonological inventory, with operators built from articulatory features via `exp` of a fixed 4-dimensional `so(4)` slice, read out as a state vector for structural metrics — explicitly "structure, not meaning."**

---

## 2. Comparison with the deterministic-vṛtti requirements

The deterministic branch requires `L(σ) → M_σ` where `M_σ` is a deterministic state-transforming operator encoding the **vṛtti**.

**What Stage A supplies:** a map `unit → M_σ` — but the domain is a **phoneme** and the operator's content is **articulatory features**, i.e. `L_phonology → M`, *not* `L_vṛtti → M`. To obtain the vṛtti table one must **replace the feature matrix `F` with vṛtti coordinates** and **extend the inventory** — that is supplying new data, not reinterpreting Stage A.

**Direct property check:**

| requirement | Stage A | verdict |
|---|---|---|
| deterministic transformation | `M_σ` deterministic orthogonal | **directly satisfied** |
| order-sensitive composition | `read_product`; G1 order-effect 1.12 vs bag 0 | **directly satisfied** |
| associativity | matrix product | **directly satisfied** |
| non-commutativity | coupling generators non-commuting (asserted) | **directly satisfied** |
| reproducibility | deterministic, no fitting, fixed generators, numpy-only | **directly satisfied** |
| compositional closure | `M_σ ∈ SO(4)`, a group ⇒ products stay in SO(4) | **directly satisfied** |
| finite operator inventory | finite, **but 14 toy phonemes ≠ the varṇa set** | **satisfied in form, wrong content** |
| operators encode the **vṛtti** | operators encode **phonology**; meaning explicitly disclaimed | **NOT satisfied** |

So Stage A satisfies the **algebraic/compositional** requirements *directly*, and fails the **content** requirement: its operators are phonological, and phonology is exactly the interpretation the current theory rejected.

---

## 3. Assumption inventory

**Already present in Stage A (would be inherited):**
- `d = 4` with the 2⊗2 tensor layout;
- **orthogonality / SO(4)** (norm preservation, *invertibility*);
- the specific **4-generator `so(4)` slice** with the baked-in "(A,B) commute / coupling doesn't" factorization hypothesis (chosen for *phonology*);
- the `exp` initializer; fixed `S0`; one operator per unit, shared, no fitting;
- **coordinates = 4 articulatory features.**

**New assumptions required to make it the varṇa table:**
- **a vṛtti-coordinate matrix** `varṇa → ℝ⁴` (does not exist; must be defined/derived) — the load-bearing new object;
- **inventory extension** to the full varṇa set (34 consonants + vowels);
- **dimensionality assumption**: that a vṛtti compresses to 4 coordinates in a specific `so(4)` slice;
- **basis assumption**: that `G_A..G_D` (a phonological factorization basis) is also the right *semantic* basis;
- a **semantic readout** (Stage A's is a metric state-vector, not a decoder);
- **semantic interpretation** of the `ℝ⁴` carrier and the operators (Stage A explicitly forbids this).

The gap between "already present" and "new" is large, and the biggest new item — a vṛtti-coordinate matrix — is precisely the object the whole program has been unable to specify.

---

## 4. Alternative deterministic realizations (existing math only)

| realization | fit to stated properties |
|---|---|
| **general linear operators `GL(d)`** | more expressive but can blow up; Stage A chose orthogonal *precisely* to avoid this. |
| **permutation operators `S_n`** | deterministic, discrete, non-commutative, finite, closed (group); maps naturally to a **finite symbolic state set** — high on *finite/discrete/interpretable*, low on graded blending. |
| **deterministic finite-state transitions (DFA transition monoid)** | each varṇa → a transition function on a finite state set; composition = function composition; the **exact point-mass limit of the Markov-kernel frame**. Strong fit to *finite/discrete/interpretable*. |
| **rotation groups other than SO(4)** — SO(2)/RotatE, SO(3), general SO(n)/U(n) | nothing in the vṛtti spec mandates 4, the 2⊗2 factorization, or that specific slice; those are Stage-A phonology choices. |
| **matrix semigroups (non-invertible)** | permit *dissipative/absorbing* vṛttis (e.g. "closure/completion" collapsing state); SO(4)'s invertibility forbids this — a real expressivity question the vṛtti spec has not settled. |

**Assessment:** for the *stated* properties (finite/discrete/interpretable), a **finite-state transition monoid / permutation realization** fits at least as well as SO(4) and is the clean point-mass limit of the kernel frame; SO(4) is the *continuous, invertible, norm-preserving* realization — richer geometrically but importing invertibility, a fixed dimensionality, and a phonological basis. No single realization dominates without first committing to whether vṛttis are *continuous vs discrete* and *invertible vs dissipative*.

---

## 5. Risks (falsification attempts)

1. **Designed for another purpose.** Stage A is a *phonological structural testbed* that explicitly disclaims meaning and labels its operators provisional. Repurposing it as the vṛtti table contradicts its own frozen charter.
2. **Its content is antithetical to the current theory.** The operators derive entirely from **articulatory features**. Reusing them = encoding **phonology** — exactly the acoustic/phonetic interpretation the theory spent many iterations rejecting ("varṇa is the letter, not the sound"). Using Stage A's *operators* would silently re-import the discarded layer.
3. **SO(4) is likely over-restrictive and over-specified.** Invertible + norm-preserving + 4-dimensional + 2⊗2 factorization are all choices with **no vṛtti-side justification**; the 4-generator slice is a non-canonical subspace of `so(4)`.
4. **The correspondence is at the level of the *algebra*, not the *values*.** Stage A shares the *shape* (operator table + ordered product + non-commutativity) with the deterministic-vṛtti spec, but the *operator values* come from a different, incompatible source. The match is **structural/analogical for the values**, mathematical only for the composition law.
5. **Freeze constraint.** Stage A is frozen (baseline `2d42bf6`); it cannot be modified in place, so "becoming" the vṛtti table would require a separate artifact regardless.
6. **Stage A failed its own G4.** Even as a phonological structural claim it is a partial null — no endorsement of the specific baked-in factorization.

---

## 6. Final recommendation — **C** (with a precise nuance)

> **C — Stage A should remain independent and frozen; a separate deterministic varṇa operator table should be built. Reuse Stage A's construction *pattern* and *null methodology*, but not its operators or features.**

**Why not A** (Stage A *is* the realization): rejected. Its operators encode phonology, its inventory is a toy set, it disclaims meaning, and SO(4) imports invertibility/dimensionality/basis assumptions the vṛtti spec does not warrant. Using Stage A's actual operators would re-introduce the acoustic layer the theory abandoned.

**Why not B** (Stage A *becomes* the realization with added assumptions): rejected as framed. "Becoming" it would mean swapping in a vṛtti-coordinate matrix, extending the inventory, and re-justifying `d`/basis — i.e. supplying entirely new inputs while *discarding* Stage A's defining content (`F`). That is building a new table that merely *borrows a construction recipe*, not reinterpreting Stage A. And the freeze forbids in-place change anyway.

**What C means concretely (and what is legitimately reusable):**
- **Keep Stage A frozen and independent** — different purpose, inventory, coordinates, and an explicit non-semantic charter.
- **Build the varṇa operator table as a separate artifact** (the existing `experiments/varna_operator/` scaffold is exactly this independent path).
- **Reuse the *methodology*, not the table:** the ordered-product engine; orthogonality-*as-a-stability-device* (optional, if a continuous realization is chosen); the `exp`-of-generators initializer *as one option among several* (permutation / finite-state monoids are equally admissible and may fit *finite/discrete/interpretable* better); and above all the **null battery — bag, random-orthogonal, relabel** — which is the transferable rigor.
- **Do not inherit** the articulatory feature chart, the 2⊗2 phonological factorization basis, `d=4`, or invertibility *by default*; those are Stage-A phonology decisions, and the vṛtti realization's dimensionality/basis/invertibility should be **left open** until the theory commits to continuous-vs-discrete and invertible-vs-dissipative.

**Prerequisite before any table is canonical (independent of A/B/C):** a **varṇa → operator-coordinate specification** must exist. Stage A does not provide one (its coordinates are phonological), so no route — including reuse — yields a *vṛtti* table until that mapping is supplied. That missing object, not the choice of operator family, is the true blocker.

> structure, not validated meaning.
