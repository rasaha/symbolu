# Canonical Primitive Representation — The Ontology Before Realization

**Status:** Theory/architecture design only. No implementation, no code, no experiments, no run, no Stage A modification, no pre-registration change. No semantic claim.

**Purpose:** Separate the *semantic representation* (ontology) from *linguistic realization*. Prior notes silently rendered the ordered primitive sequence as **English gloss concatenation**, which is already a realization choice. This note derives the representation the ontology actually ends at — the "AST / logical form," not the rendered sentence — and proves a consequence that reshapes any experiment.

---

## 1. The canonical representation

Let `P = {p₁,…,p_K}` be the set of primitive vṛttis, treated as **opaque atoms**: each has an *identity* (distinctness from the others) and **nothing else** — no gloss, no coordinates, no decomposition. Since `varṇa → primitive` is a fixed map `τ: Σ → P`, the canonical representation of a word is its varṇa sequence relabeled to atom-IDs:

```
word  →  ⟨ p_{σ₁}, p_{σ₂}, …, p_{σn} ⟩   ∈  P*
```

i.e. an element of the **free monoid `P*`** — a flat, ordered tuple of typed leaves. It is the AST/logical-form level: no internal nodes, because operators/relations would be structure the ontology forbids.

**A gloss is a rendering, not the atom.** "hope", "āśā", "espoir", "longing" are all renderings of the same atom `p_ka`; the canonical form commits to none.

### It satisfies the required properties
1. preserves order ✓ (ordered tuple)
2. preserves primitive identity ✓ (atoms are identified)
3. no English grammar ✓ (no words, no connectives)
4. no relation labels ✓ (flat list; no edges)
5. no hidden coordinates ✓ (atoms opaque, non-decomposable)
6. no operators ✓ (juxtaposition only; composition is not a function applied)
7. deterministic ✓ (fixed `τ` + word → unique tuple)
8. multiple NL renderings possible ✓ (each atom → many glosses/languages; connectives are supplied only at realization)

It is **minimal**: removing anything drops either order or identity.

## 2. What it excludes (by construction)
No English glosses; no grammar/connectives; no relation labels or edges; no coordinates; no operators; no polarity/intensity; no phonetic features. The connectives ("by", "through", "causing", …) are **decode-time realization artifacts**, not part of `P*`.

## 3. Relabeling-invariance theorem

> **Theorem.** Let `τ: Σ → P` be the real assignment and `τ' = π∘τ` a scrambled assignment, where `π` is a permutation of the atoms `P`. For any function `F` on `P*` that is **invariant under permutations of the atom set** — which includes **every sequence-similarity measure over opaque atoms** (edit distance, n-gram/subsequence overlap, alignment scores) — we have
> `F(τ*(w)) = F(τ'*(w))` for every word `w`.
> Hence no such `F` can distinguish the real table from a scrambled one.

**Proof sketch.** `τ*` applies `τ` letterwise; `τ'* = π∘τ*`. If `F(π·s) = F(s)` for all `s ∈ P*` (permutation invariance of `F`), then `F(τ'*(w)) = F(π·τ*(w)) = F(τ*(w))`. Sequence-similarity over opaque tokens depends only on the *pattern of coincidences* (which positions carry the same atom) and the order of those coincidences — both invariant under renaming atoms. ∎

**Caveat (non-injective `τ`).** If two varṇas map to the *same* atom, a scramble that changes the **kernel** of `τ` (which varṇas collide) is not a pure relabeling and can change `F`. So the *only* opaque-testable feature of the assignment is its **partition of `Σ`** ("which varṇas share a primitive"). For a (near-)injective real lexicon this residue is (near-)empty.

## 4. Consequence: the assignment is invisible at the canonical level

The canonical representation is **semantically inert**:

- Opaque atoms carry **no content** a meaning-blind realizer can compare against candidate meanings.
- By the theorem, the **real-vs-scrambled contrast — the entire basis of falsifiability — is invisible** on `P*` (any relabeling-invariant statistic is identical for real and scrambled). What little survives (the partition) is near-empty for the real table and, where non-empty, is confounded with morphology (shared letters ↔ shared meaning).

**Therefore the theory's actual content — that `ka` denotes *hope* specifically — lives entirely in the content-attachment, which is realization.** There is **no realization-free test of the assignment.**

## 5. English-gloss concatenation is a realization, not the ontology

Rendering `⟨p_ka, p_ma⟩` as "hope … giving-latitude" injects a specific language's vocabulary, tokenization, and word-meanings. It is one realization `R` of the canonical form, not the canonical form itself. Any signal measured on it is entangled with that realization's semantics (e.g. English embedding geometry).

## 6. What follows for experiments

Because the assignment is testable only through realization, an experiment cannot operate on `P*` alone, and it must not privilege a single realization. The correct move is to make realization an **explicit, varied layer** and define the **ontological signal as the component invariant across realizations** (a real-vs-scramble advantage that survives re-rendering). See `PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`.

> structure, not validated meaning.
