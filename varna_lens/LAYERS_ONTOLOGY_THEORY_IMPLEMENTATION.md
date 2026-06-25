# Layers: Ontology · Reading Theory · Implementation — a boundary document

> **Type:** boundary / specification document. **Date:** 2026-06-25.
> **Purpose:** prevent a recurring conflation between (a) computational results about the *currently
> specified* reading function ρ and (b) the *completed/intended* acoustic theory ρ\*. This document changes
> no code, no lexicon, no tests, and re-runs no experiments. It only fixes scope.

## 0. Core principle

> **A computational class is a property of a *specified function*, not of a *domain of inquiry*.**

Consequences, stated once and relied on throughout:

- The **current ρ** is a fully specified function, so it **can** be classified (and has been: finite-state /
  subsequential / minimizable — see §3).
- The **completed acoustic theory ρ\*** is **not yet a mathematical function** — it is an open research
  target. An object with no definition has **no** computational class. Therefore ρ\* **cannot** be
  classified yet, in either direction (neither "finite-state" nor "not finite-state").
- Asking "what computational class is the acoustic theory?" is **premature**, not merely unanswered. It
  becomes answerable only once ρ\* is specified, and must then be **re-derived** from that specification.

## 1. The three layers

### Layer 1 — Acoustic ontology (*what the varṇas represent*)
Asks: What do varṇas represent? What are the source-derived attributes? Are the sound→propensity
associations real?

- **Mostly scientifically open.** Source-derived and interpretive.
- Contains the lexicon, glosses, and ontology (binding/liberating states, vṛtti/elemental metadata).
- **Does not by itself define a computational class.**
- The **finite varṇa inventory** is a **robust ontological commitment**.
- Specific **glosses and polarity meanings are gauge / source choices** unless empirically validated.

### Layer 2 — Reading theory ρ (*the abstract morphism*)
Asks: Given a word / varṇa sequence, what abstract reading maps it into signs, poles, tendencies, or
profiles?

- The **current ρ is specified.** The **final / intended ρ\* is still open.**
- The scientific question is the **selection problem: which ρ is correct?**
- The **computational class depends on the dependency structure of the chosen ρ** (see §6 dependency map).

Illustrative (each is a *candidate* ρ, not a claim about ρ\*):

- radius-1 local deterministic ρ → **finite-state / subsequential FST**.
- bounded context radius-*k* ρ → **still finite-state**.
- finite whole-word summary → **still finite-state**.
- unbounded nesting / recursion → **pushdown / tree transducer / context-free** class.
- unbounded counting → **counter / Petri-style systems or non-rational mappings**.
- global fixpoint or optimization semantics → **weighted constraint systems / factor graphs / fixpoint
  semantics**.

### Layer 3 — Implementation (*Python / FST / JSON*)
Asks: Does the implementation faithfully realize the *currently specified* ρ?

- **Well-characterized** for the current implementation.
- Current implementation is **local, deterministic, finite-alphabet, bounded-lookahead**.
- The **current automata / minimization result applies here and to the current candidate ρ.**
- It **does not classify the completed acoustic theory.**

## 2. Correction of previous phrasing

Earlier analysis was at times phrased as if it classified "the acoustic theory." That phrasing is corrected:

> The theorem is **not**: "the acoustic theory is finite-state."
> The theorem **is**: "the **currently specified** reading function ρ is finite-state **under the current
> assumptions** of finite alphabet, locality, bounded lookahead, and determinism."

And:

> **If locality or determinism is changed, the computational class must be re-derived.** There is no
> conservation law keeping a redefined ρ inside the finite-state class, and no guarantee it leaves it; the
> outcome follows from *which* assumption changed and *how* (§6).

## 3. Conditional theorem (scoped)

> **┌─────────────────────────────────────────────────────────────────────────────────────────┐**
> **Conditional theorem.**
> If the reading morphism ρ is **deterministic**, over a **finite alphabet**, and **bounded-context /
> local**, then ρ is realizable by a **subsequential finite-state transducer**. For the current **radius-1**
> implementation, the **minimal realization has size Θ(|Σ_C|)**, with **gemination / context memory** as the
> main source of non-constant state.
>
> *Scope:* this theorem applies **only** to the current ρ, or to future ρ variants satisfying the **same**
> assumptions. It does **not** apply to the unspecified completed theory ρ\*.
> **└─────────────────────────────────────────────────────────────────────────────────────────┘**

## 4. Robust-vs-contingent ledger

| Category | Claim | Survives future enrichment of ρ? |
|---|---|---|
| **Robust across any chosen ρ** (framework / schema theorems) | `Adm ↠ Z ↪ R` factorization | **Yes** |
| | `Z` determined by `ker(ρ)` | **Yes** |
| | carrier determined by equivalence classes of readings (coimage) | **Yes** |
| | content / relabeling is **gauge** | **Yes** |
| | future operators must respect the kernel / congruence if they act on `Z` | **Yes** |
| | firewall / no-truth-field remains structural | **Yes** |
| **Contingent on current assumptions** (current local deterministic ρ only) | finite-state / rational transduction | No — re-derive if assumptions change |
| | subsequential FST | No |
| | Θ(|Σ_C|) minimal size | No |
| | aperiodic / star-free / FO-definable status | No |
| | bimachine form | No |
| | gemination as sole / primary complexity source | No |
| | finite syntactic monoid | No |
| | bounded lookahead | No |
| **Fragile / instance-level** (do **not** generalize) | "ρ is not a monoid homomorphism" | No — instance boundary behavior |
| | specific minimal-state count | No |
| | specific boundary behavior | No |
| | specific examples from `RULES.md` | No |
| | any result depending on current lexicon polarity (before/after correction) | No |

## 5. Assumption table

| Assumption | Used in automata proof? | Status |
|---|---|---|
| finite alphabet Σ | yes | **robust ontology commitment** |
| locality / bounded context | yes | **current specification choice** |
| bounded lookahead | yes | current specification consequence |
| determinism | yes | **current specification choice** |
| single left-to-right pass | **not essential** | implementation convenience |
| current lexicon glosses | **no** (for the automata class) | source / gauge layer |
| empirical truth of attributes | **no** | **open scientific question** |

## 6. Dependency-class map (which enrichments stay finite-state)

The class is governed by the *nature of the dependencies* (equivalently, the logic needed to define the
pole-assignment). Which enrichments keep ρ finite-state and which leave it:

- **bounded local context** → finite-state.
- **finite global summary** (e.g. a bounded whole-word field / valence tally with finitely many values) →
  finite-state.
- **finite set of seen symbols** (tracking *which* of a finite Σ appeared — distinctness, not count) →
  finite-state.
- **modular counting** → regular, but may **leave aperiodic / star-free**.
- **unbounded exact counting** → **not finite-state** in general.
- **recursion / nested structure** → **pushdown / tree transducer** (context-free or beyond).
- **global optimization / fixpoint** → **constraint / factor / fixpoint system**.
- **probabilistic ambiguity** → **weighted / nondeterministic transducer or probabilistic model**.

Threshold summary: bounded-memory, finite-distinction dependencies (even global ones over finite Σ) stay
**regular**; **unbounded counting, unbounded nesting/recursion, or global fixpoint/optimization** push ρ up
the hierarchy.

## 7. Official project-status wording

> The current Varṇa Lens reading rule is realizable as a finite-state transducer. **This is a theorem about
> the currently specified local deterministic reading function ρ, not a classification of the completed
> acoustic theory.** The computational class of the completed theory remains **open** until the final
> reading morphism ρ\* is mathematically specified.

## 8. Boundary note (canonical short form for cross-references)

> Automata / minimization claims classify the current ρ implementation only. They do not classify the
> completed acoustic ontology or future reading-theory variants.

## 9. What this document does and does not do

- It **scopes** existing results; it does not retract them. The finite-state / minimization theorem stands,
  correctly bounded to Layer 3 and the current Layer-2 candidate.
- It does **not** claim ρ\* is finite-state, nor that ρ\* is non-finite-state.
- It does **not** rescue, revive, or weaken any empirical / falsification result. Prior NO_SIGNAL and other
  outcomes are untouched and remain governed by their own pre-registrations.
- The central open question is **Layer 2's selection problem** (which ρ), and through it the computational
  class of ρ\*.

## 10. Final status statement

> The finite-state / minimization result is **preserved, but now correctly scoped**: it is a theorem about
> the **current** local deterministic reading function ρ and its implementation, **not** a theorem about the
> completed acoustic theory. The final theory's computational class **remains open** until the intended
> reading morphism ρ\* is specified and re-analyzed.
