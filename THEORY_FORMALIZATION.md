# Symbol-U — Theory Formalization

> **Type:** scientific foundation document (research track). No code. No implementation.
> Companion documents: `FALSIFICATION_STRATEGY.md`, `SCIENTIFIC_ROADMAP.md`.
> Purpose: state the *original* Symbol-U theory, stripped of implementation, precisely
> enough to reason about whether it is falsifiable. This document neither defends nor
> refutes the theory.

## 0. Framing

Stripped of implementation, Symbol-U is a **phonosemantic (sound-symbolism) theory**: a
specific, strong instance of the claim that speech sounds carry non-arbitrary meaning.
Sound symbolism is a real, studied area of linguistics (Köhler bouba/kiki; Sapir mil/mal
size effect; phonesthemes; Blasi et al. 2016 cross-linguistic sound–meaning biases).
Framing Symbol-U this way is what makes falsification tractable: it inherits established
psycholinguistic and cross-linguistic methods.

## 1. Assumptions

- **A1 (Inventory).** There is a finite set of phonological atoms (varṇas) `V`.
- **A2 (Intrinsic attributes).** Each `v ∈ V` carries an attribute vector `a(v)` (pole:
  binding/liberating; essence; elemental class) **derived from the sound's articulatory /
  acoustic form**, not assigned by convention.
- **A3 (Partial universality).** `a(v)` is at least partly shared across humans / languages;
  otherwise it is indistinguishable from an arbitrary lexicon.

## 2. Axioms (the distinctive, load-bearing commitments)

- **Ax1 (Non-arbitrariness).** `a(v)` is recoverable from the *sound* of `v` — the
  sound→attribute link is reproducible without conventional lookup.
- **Ax2 (Compositionality).** An utterance's reading is an **order/structure-sensitive**
  function of its attribute sequence: `ρ*(v₁…vₙ) = F(a(v₁), …, a(vₙ))`, with `F` **not** a bag.
- **Ax3 (Emergence).** `F` yields properties absent from the individual `a(vᵢ)` — the
  "essence chain," CSR (contextual semantic resonance), contextual resonance.

## 3. Derived claims

- **DC1.** Utterances with similar attribute composition share "acoustic meaning."
- **DC2.** That meaning correlates with human responses to the **sound**, not to lexical
  glosses. *(This is the inverse of an English-lexical-meaning yardstick.)*
- **DC3.** In a language where the theory holds, varṇa composition predicts attested
  semantic/affective properties **above chance** and **above arbitrary relabelings**.

## 4. Predictions

The theory's *unique* predictions all concern **lexically-empty stimuli** (pseudowords)
and **cross-speaker universality** — the two regimes ordinary semantic models cannot reach.
Enumerated and operationalized in `FALSIFICATION_STRATEGY.md` §3.

## 5. What ρ\* must satisfy — required properties vs. implementation choices

| Property | Status | Note |
|---|---|---|
| Deterministic given the varṇa sequence | **Required** (A2) | intrinsic attributes |
| **Order / structure-sensitive (non-bag)** | **Required** (Ax2) | the prior implementation's bag aggregation violated this |
| Sound-grounded ⇒ **language-independent at the phoneme level** | **Required** (A3) | identical phoneme sequences in different languages → identical reading; strong and testable |
| Beats random relabeling of `a(·)` | **Required** (Ax1/A3) | else it is an arbitrary lexicon |
| Sensitive to sound change; stable under sound-preserving change | **Required** | the *inverse* of a meaning-semantics yardstick |
| English input / transliteration | Implementation | not in the theory |
| Specific features / aggregation | Implementation | — |
| Continuity, invertibility, the specific hierarchy tree | Implementation / open | not entailed |
| **The actual form of `F`** | **UNSPECIFIED by the theory** | the fatal gap (§6) |

## 6. The fatal gap (the central conclusion)

Ax2/Ax3 assert that `ρ*` exists and is emergent, but **the theory never defines `F`.** The
project's own boundary document concedes ρ\* "is not yet a mathematical function… an open
research target."

> **You cannot falsify a function that has not been defined.**

Therefore:

- The theory's **atomic** claim (**Ax1**: each varṇa has a non-arbitrary, sound-derived
  attribute) **is falsifiable today** — it needs only `a(·)`, which already exists.
- The theory's **distinctive** claim (**Ax2/Ax3**: emergent compositional acoustic meaning,
  ρ\*, CSR) is **not currently falsifiable** — not "unfalsified," but *unstated*.

This is a deficiency of the theory's **current statement**, not evidence for or against it.

## 7. Three levels of claim (used throughout the research track)

- **Level A — a useful semantic representation exists.** Supportable by any discrimination
  result (even sentiment). Weakest.
- **Level B — that representation reflects the proposed ontology.** Requires the
  **shuffle/relabel ablation** (real ≫ permuted). Only the relabel control separates B from A.
- **Level C — the ontology derives specifically from Sanskrit varṇa acoustic semantics.**
  Requires gloss-free **acoustic-only** signal, **cross-linguistic** evidence, and Sanskrit
  attestation. Hardest.

All prior work (v3, v4, O1.5, policy experiments) bears only on **Level A**, on **English**,
using **glosses** — the three things the theory's unique claims explicitly route around.

## 8. Implementation caution (binding for the research track)

**No further English LLM-controller or policy work should proceed** until either:
- **S1/S2/S3** (see `SCIENTIFIC_ROADMAP.md`) provide support for the **atomic** claim, or
- **S0** specifies `ρ*` well enough to test the **emergent** claim.

Until one of those holds, any implementation can only re-test Level A on English — which has
already failed — and cannot bear on the theory.
