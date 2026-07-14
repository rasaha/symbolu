# Bare-Word Symbolic Resonance (BSR) — Preregistration V1

**Documentation-only preregistration.** No experiment is run, no word is selected, no word is scored, no mapping
is modified, no prior experiment is reinterpreted. This document defines **one methodology only** — Bare-Word
Symbolic Resonance (BSR) — and freezes its rules before any evaluation.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. **This is not a scientific-validation protocol, not a
linguistic proof, not a Barnum evaluation, not a shuffled-mapping study, not a uniqueness study, not a
feature-lift study, and not a causal sound-symbolism study.** Those remain independent research programs (§9).

**Frozen inputs (read-only; not modified by this prereg):** parser `sanskrit_stage1_parser.py` (`PARSER_SPEC_v1`),
lexicon `frozen/varna_native_stage1_merged_v3.json` (`65116f37…`; 33 confirmatory-backbone consonants, each with
its verbatim frozen binding gloss), consonant-primary arm.

---

## 1. Objective (frozen verbatim)

> **Determine whether the stable, ordinary, unqualified meaning of an attested Sanskrit bare word naturally
> accounts for the frozen pronunciation-derived varṇa mappings without semantic supplementation.**

This is called **Bare-Word Symbolic Resonance (BSR)**. Nothing else.

A positive BSR result means **only** that the frozen mappings admit a coherent symbolic interpretation of the
ordinary bare word. It makes no claim beyond that (see §7).

## 2. Scope

- **In scope:** whether the bare word's ordinary meaning naturally accounts for each frozen varṇa→gloss mapping,
  and *which symbolic relationship* (§4) does the accounting.
- **Unit of evaluation:** each mapped **consonant occurrence** of an attested Sanskrit word (occurrence-level,
  multiplicity preserved), against its **verbatim frozen binding gloss** from the pinned lexicon.
- **Out of scope (see §8):** objective truth, linguistic causation, historical correctness, exclusivity,
  uniqueness, shuffled superiority, statistical significance, downstream ML usefulness, Barnum susceptibility, and
  scientific falsification.
- BSR is a **descriptive interpretive** methodology. It describes whether a coherent symbolic reading exists; it
  does not test whether that reading is correct, necessary, unique, or predictive.

## 3. Bare-word rule

The evaluator asks **one** question, and only this question, for each mapping:

> **Does the ordinary bare word naturally account for this mapping?**

"Bare word" = the stable, ordinary, unqualified prototype meaning of the attested word — fixed **before** the
mapping is seen. The evaluator **must not** rely on, and resonance is **weak or absent** if the account requires,
any of:

- added adjectives (e.g. "cruel greed," "mad greed");
- additional nouns;
- external actors (e.g. "a person who…");
- historical stories or anecdotes;
- exceptional or extreme situations / rare subtypes;
- symbolic inventions not present in the ordinary meaning;
- any semantic rescue or supplementation.

If the ordinary bare word accounts for the mapping **without** such supplementation, resonance is present; the
degree is scored in §5. If supplementation is required, resonance is weak (partial supplementation) or absent (no
story-free account).

## 4. Relationship taxonomy (descriptive only — never a verdict)

Accounting may occur through **any legitimate symbolic relationship**. The evaluator records **which** relationship
naturally exists. **No relationship type is intrinsically better than another**; the type is descriptive metadata,
not a score input and not a pass/fail signal.

| Type | The bare word accounts for the mapping by … |
|---|---|
| **Embodiment** | being / manifesting the mapped state |
| **Implication** | logically entailing it |
| **Characteristic expression** | characteristically expressing or displaying it |
| **Natural consequence** | naturally producing or leading to it |
| **Opposition** | being the natural contrary of it |
| **Resolution** | resolving / dissolving / transcending it |
| **Regulation** | naturally governing, restraining, or moderating it |
| **Containment** | naturally holding or encompassing it |

Explicit rulings, frozen:
- **Embodiment is not failure.** A word that *embodies* its mapping accounts for it and resonates.
- **Opposition is not failure.** A word that *opposes* its mapping accounts for it and resonates.
- **Resolution is not mandatory.** A word need not transcend its mapping to resonate.
- A mapping does **not** resonate less merely because a *different* relationship type, or a different mapping,
  could also fit (that is a §8/§9 question, excluded here).

## 5. Component scoring — Symbolic Resonance Score (frozen scale)

Each component (one mapped consonant occurrence) receives one Symbolic Resonance Score, based **solely** on how
naturally the ordinary bare word accounts for the frozen mapping (via whichever §4 relationship applies):

| Score | Meaning |
|---|---|
| **100** | The mapping is **directly and characteristically present** in / accounted for by the bare word. |
| **75** | **Strongly implied** by the ordinary meaning. |
| **50** | **Plausible, but requires interpretation.** |
| **25** | Requires **substantial qualification, an exceptional case, or an external actor**. |
| **0** | **Cannot be supported** without adding external meaning. |

The score depends **only** on the bare-word account (§3). It must **never** depend on shuffled/random mappings,
comparative packets, uniqueness, or exclusivity (§6).

**Per-component record (mandatory).** For every mapped component the evaluator records, before aggregation:
1. the **frozen mapping** (consonant → verbatim binding gloss);
2. the **relationship type** (§4);
3. **supporting evidence** — why the bare word naturally accounts for it (no supplementation);
4. **opposing evidence** — what in the bare word resists or fails to account for it, or where supplementation
   would be needed;
5. the **Symbolic Resonance Score** (§5 scale).

A component score recorded without supporting evidence is **invalid**.

## 6. No Barnum criteria (frozen)

The Symbolic Resonance Score must **never** depend upon, and this methodology does **not** use as any criterion:

- shuffled mappings;
- random mappings;
- comparative packets;
- uniqueness;
- exclusivity.

Such analyses may be documented in **future, separate** research (§9) but are outside the scope of this
preregistration and must never alter a BSR score or verdict.

## 7. Combined resonance

After all components are **independently** scored (§5), the evaluator records **whether the components reconcile
into one coherent symbolic understanding of the word** — i.e. whether the per-component accounts cohere into a
single symbolic reading of the bare word.

- Combined resonance is **explanatory only**. It **may explain** how the component resonances fit together.
- Combined resonance **may never overwrite** component resonance. Component scores are fixed at §5 and are not
  revised in light of the combined reading.
- If combined resonance is high while component resonances are weak, that is recorded as an **explanatory
  observation**, not a promotion of the component scores.

## 8. Interpretation limits (frozen)

A **positive** BSR result means **only**: *the frozen mappings admit a coherent symbolic interpretation of the
ordinary bare word.* It does **not** claim any of:

- linguistic necessity;
- historical origin;
- metaphysical truth;
- scientific proof;
- predictive superiority;
- exclusivity or uniqueness;
- causal sound-symbolism.

A **negative/weak** BSR result means only that the bare word does not account for the mapping without
supplementation — it is not a claim about linguistic falsity.

**Explicit exclusions.** This preregistration does **not** evaluate: objective truth · linguistic causation ·
historical correctness · exclusivity · uniqueness · shuffled superiority · statistical significance · downstream
ML usefulness · Barnum susceptibility · scientific falsification. Each is a separate study; if performed later,
each must remain separate and must **not** alter the BSR verdict.

## 9. Relationship to other research tracks

BSR is **Track A**; scientific evaluation is **Track B**. They are distinct preregistered tracks and must not
drift into one another.

- **Track A — Symbolic Resonance (this prereg):** "Does the ordinary bare word admit a coherent symbolic
  interpretation under the frozen mappings?"
- **Track B — Scientific Validation (separate):** "Is that interpretation specific, predictive, unique, or better
  than alternatives?"

The following remain **separate** research programs; this preregistration **neither replaces nor invalidates**
them, and introduces a **different research question**:

- the prior **Resolution** experiments (V1 / V1.1 transcendence reading, and the expanded stress-test);
- the **Feature-Lift** study (downstream ML utility, shuffled-mapping ablation);
- **B1.12** (and all B1.x work);
- **Shuffle / Bare-Word-Resolution-with-shuffle** probes;
- any **Scientific-Validation** protocol (uniqueness, significance, causation).

Results from Track B, if later obtained, must **not** alter a BSR resonance verdict, and a BSR verdict must **not**
be cited as Track-B evidence.

## 10. Readiness

**`READY_FOR_WORDLIST_PRECOMMITMENT`.** The BSR objective (§1), scope (§2), bare-word rule (§3), relationship
taxonomy (§4), component scoring (§5), no-Barnum rule (§6), combined-resonance rule (§7), interpretation limits
(§8), and track separation (§9) are frozen outcome-blind. The **next gate — a separate step — is precommitting an
attested bare-word list** (stable ordinary meanings, fixed before any component is seen), after which §3–§7 may be
executed. No word is selected or scored here.

## Guardrails
Documentation-only preregistration of a single methodology (BSR). No experiment, no word selection, no scoring, no
modification of the parser, mappings, lexicon, or any prior/frozen artifact, and no reinterpretation of previous
experiments. Symbolic resonance (does a coherent symbolic reading exist), not scientific validation, not linguistic
proof, not Barnum, not uniqueness, not causation. Structure, not validated meaning.
