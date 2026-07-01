# Correction Note — Relation as Decode-Time Realization Artifact (revises RELATION_AXIOM_R)

**Status:** Theory/architecture correction. No implementation, no code, no experiments, no run, no Stage A modification, no pre-registration change. No semantic claim.

**Purpose:** This note **revises** the conclusion of `RELATION_AXIOM_R.md`. That note argued the missing structural constraint is a coordinate-free relation system `R` (a monoid congruence). On further analysis that over-reached: it conflated *"a relation must exist"* (true) with *"a relation must be a stored ontological object"* (false). The correction is recorded here.

---

## What is withdrawn

`RELATION_AXIOM_R.md` treated `R` as an **ontological object** the theory must contain (a stored congruence / edge labels / a hidden semantic algebra between vṛttis). That is **withdrawn**:

- **Stored relation labels are not mathematically required.**
- **`R` as an ontological object is withdrawn.**
- A relation/connective ("by", "through", "causing", "leading to", …) can be a **decode-time realization artifact**, produced during natural-language realization rather than stored between primitives.

The prior proof established only that *meaning is not a function of the raw primitive list under the identity composition* — i.e. composition is non-trivial. It did **not** establish that the relation must be a stored object. The relation must exist **as a computation**, not **as an object**.

## What remains necessary (the conserved quantity)

Composition is not eliminated; it is **relocated**. Let composition produce a state `S(w)` and realization be a decoder `D`. The compositional/relational content is conserved as a **composition/realization function `M`** (equivalently the decoder `D`), and it must live somewhere:

- **Case A — `S(w) = T(w)` (only the ordered primitives).** The connective is inferable iff the realizer `D` implements the theory's composition semantics `M`; "ordered primitives" alone do not supply `M`.
- **Case B — `S(w) ⊋ T(w)` (composition builds a richer latent state).** Connectives emerge at decode time, but the relational content now lives in `S` (put there by the composition). This is what an LLM is: the hidden state is not the bag of token embeddings; a trained composition encodes the relations. Relations emerge in decoding *because* composition already encoded them.

**Conserved-quantity statement:** the relation-content never vanishes; it is either **(i) specified by the theory** (a composition `M`, i.e. hidden structure relocated into composition) or **(ii) borrowed from an external, fixed realizer `D`** (then the varṇas contribute only the ordered primitive sequence).

## The simpler, falsifiable form

If `D` is an **external, fixed, meaning-blind realizer** (general language competence / an LLM decoder, chosen in advance, with no access to the target meaning), then:

- there is **no stored `R`**, no edge labels, no hidden vṛtti algebra;
- the varṇa theory's **entire** content reduces to: *"the ordered primitive sequence, composed by a fixed meaning-blind realizer, recovers word meaning better than a scrambled primitive table."*
- This is **non-circular** (realizer fixed in advance and meaning-blind) and **fully falsifiable**.

Consequence and cost: because all compositional power is moved into an external realizer that knows nothing about vṛttis, the **varṇas must carry recoverable signal in the raw ordered list itself.** The theory is simpler, but its predictive burden rests entirely on the primitive sequence.

## Relevant evidence (empirical, not logical)

A blind judge given only the ordered primitive glosses and asked to recover the word's meaning **is** this fixed external, meaning-blind realizer. The pre-registered acoustic-signal / lexical-recovery test in this repository ran exactly that operationalization and returned **real ≈ scrambled (NO_SIGNAL)** (`RESULTS_ACOUSTIC_SIGNAL.md`, and the corrected-lexicon re-run). Therefore:

- this is **relevant evidence against the operationalization** (the simplest external-realizer form of the theory), but
- it is **not a logical refutation** of the model. The model is logically coherent; it is the *empirical* record that is, so far, negative.

## Revised bottom line

- **`R` as an ontological object: withdrawn.** Stored relation labels are not required.
- **Relation/connective: admissible as a decode-time realization artifact.**
- **What remains necessary: a composition/realization function `M` (or external realizer `D`)** — specified by the theory, or borrowed from a fixed external realizer.
- **If `D` is external and fixed, the ordered primitive sequence must carry recoverable signal**, and the theory becomes simpler and falsifiable.
- **The scrambled-table lexical-recovery nulls are relevant evidence against this operationalization, not a logical refutation.**

This supersedes the "R is the (form of the) missing constraint" framing in `RELATION_AXIOM_R.md`: the missing constraint is not a stored relation but a **composition/realization function**, which may be external — and when it is, the theory is simpler and directly testable.

> structure, not validated meaning.
