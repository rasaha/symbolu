# B1.4b′ — Why Word Identity Was Intentionally Hidden From the Scorer

**Status:** Clarification memo (docs-only). No code, no run, no re-scoring.
**The screening result stands: `NULL_RETURN_BOTTOM`. It is not reinterpreted here.**
**No semantic success. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No `ONTOLOGICAL_SIGNAL`. Original B1.4b remains blocked.
Track B remains blocked. Structure, not validated meaning.**

Related: `B1_4B_PRIME_SCREENING_OPERATOR_COMMANDS_EXECUTED.md` (`880ad1a`),
`B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md`, `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`.

---

## 1. The concern, stated fairly

A reasonable concern was raised: *"the experiment failed because it avoided showing the word — the word would
have given the signal."* This memo explains why that is **not** a flaw but the **whole point** of the design,
and what the null does and does not mean.

## 2. Yes — exposing the word would likely give strong signal (and that is exactly the problem)

**Confirmed:** if the scorer were shown the actual word/concept label (`"lemon"`, `"canoe"`, …), a decoder
would almost certainly predict the McRae attribute vector well. But that is **trivially** true and **proves
nothing about Symbol-U**, because the word label *is the concept's identity*. Predicting `lemon`'s features
from the string `"lemon"` is predicting a concept's attributes from a pointer to that exact concept — the
attributes are looked up, not derived.

## 3. What "show the word" would actually test — lexical identity, not the structural hypothesis

Feeding the word label to the decoder would measure one (or both) of:

- **Lexical identity / lookup** — a one-hot-ish pointer to the concept, whose attributes are a table lookup;
- **Memorized distributional semantics** — if a word embedding stands in for the label, it re-imports meaning
  learned from massive text co-occurrence.

Either way, the "signal" comes from **already knowing which concept it is** (and what it means), not from any
**Stage A′ / F-3 structural** property of the word's sound. That is a different hypothesis — one nobody
doubts — and it is precisely the **gloss/identity leakage** the L2 rulebook and the hardened varṇa-attribute
rules forbid (a decoder that "sees the word" reintroduces the confound the whole program exists to exclude).

## 4. Why B1.4b′ restricts the candidate arm to phoneme/operator-derived features

The Symbol-U claim under test is **structural**: that a word's **varṇa/phoneme sequence**, run through the
frozen operator layer (Stage A′ → `M_σ`) and summarized as **F-3 operator-interaction features**, carries
attribute-relevant structure. To test *that*, the candidate arm `A_F3_REAL` must be a function **only** of the
sound structure — **not** the word's identity or dictionary meaning. Hiding the word identity is not a handicap;
it is the **necessary condition** for the result to be about Symbol-U at all. If identity leaked in, a "win"
would be uninterpretable — you could never tell whether the operators mattered or whether the decoder simply
recognized the word. The full baseline suite (phonology, bag, shuffle, random-relabel, length/frequency,
sentiment, chance) exists for the same reason: to strip away every non-structural way of predicting `Y`.

## 5. What the null actually means

**`NULL_RETURN_BOTTOM` means:** the tested **structural representation** (Stage A′ operators → F-3), evaluated
**without** lexical identity, **did not predict** the independent McRae attribute norms above chance — and
neither did the phonology or order baselines (every arm sat at ~0.05 CV). In plain terms: *the sound-structure,
by itself, does not carry detectable signal for these attributes.* That is an honest, informative negative about
the **structural hypothesis** — which is the only thing B1.4b′ set out to test.

## 6. What the null does NOT mean (no rescue, no overreach)

- It does **not** mean "the experiment failed because the word was hidden." Hiding the word was **required**;
  showing it would have tested a different, uninteresting question.
- It does **not** become a positive if you now add word identity — that would be measuring lexical lookup, not
  Symbol-U.
- It is **not** semantic success, **not** `L1_L2_L3_ATTRIBUTE_SIGNAL`, **not** `ONTOLOGICAL_SIGNAL`. The
  `NULL_RETURN_BOTTOM` stands exactly as recorded.

## 7. Optional future diagnostic — `WORD_ID_UPPER_BOUND_CONTROL` (docs-only proposal; NOT Symbol-U evidence)

For interpretive context only, one *could* later run a clearly-labelled **upper-bound control** that decodes
McRae `Y` from **word identity** (a one-hot concept id, or a fixed pre-trained word embedding) at matched
capacity. Its purpose and framing:

- **Purpose:** quantify the ceiling — how predictable the McRae attributes are *when concept identity is fully
  available* — so the structural arms can be read against that ceiling (e.g. "F-3 recovered ~0% of the
  identity-available ceiling").
- **Explicitly NOT Symbol-U evidence:** any score it produces reflects **lexical identity / memorized
  semantics**, not varṇa/operator structure. It **cannot** emit `L1_L2_L3_ATTRIBUTE_SIGNAL` and must never be
  compared *as if* it validated Symbol-U. It would be reported as a separate `WORD_ID_UPPER_BOUND_CONTROL`
  number, a denominator for interpreting the null — not a result of the hypothesis.
- **Gating:** docs-only proposal here; it would need its own pre-registration, would not touch the frozen
  screening result, and would change nothing about `NULL_RETURN_BOTTOM`.

---

> B1.4b′ did not fail because word identity was hidden; hiding word identity was necessary to test the
> structural hypothesis. The screening result remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
