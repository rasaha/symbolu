# O1.5 Failure Localization — Where Semantic Meaning Is Lost

> Forensic investigation only. **No new reading, no modification to the reading/gate, no
> attempt to improve O1.5, no API.** All numbers are measured (reproducible:
> `python -m symbolu_neural.o1_5_construct_gate.forensic_localization`). The question is
> *where* meaning is lost, not *how* to recover it.

## Headline

Meaning is lost at **two independent stages**, both *outside* the essence/pole computation:

1. **Grapheme→varṇa decomposition (Stage B)** destroys *lexical* meaning — synonyms become
   as unrelated as random words.
2. **Final aggregation (Stage D)** destroys *compositional* meaning — the reading is a
   pure bag; word order is gone.

The pole/essence lexicon (Stage C) adds only weak signal and cannot compensate for either.

## 1. Stage-by-stage audit (measured)

**M1 — Stage B is sound-bound (varṇa-key Jaccard distance):**
| pair type | varṇa-key distance |
|---|---|
| synonyms (same meaning, diff sound) | **0.82** |
| random different words | **0.84** |

Synonyms share *as few varṇas as random words*. The varṇa sequence is a function of
**spelling/sound only**; semantic relatedness is **absent at decomposition.** "happy" and
"joyful" are as varṇa-disjoint as "happy" and "quantum."

**M2 — at the reading level, sound dominates meaning ~12:1 (isolated):**
| perturbation (isolated) | reading distance | want |
|---|---|---|
| same meaning, **different sound** (synonyms) | **2.31** | low |
| **different meaning**, similar sound (rhymes) | **0.18** | high |
| different meaning + different sound (antonyms) | 4.55 | high |

The clean comparison holds one variable fixed: change **sound** (meaning fixed) → reading
moves **2.31**; change **meaning** (sound ~fixed) → reading moves **0.18**. The reading is
**~12× more sensitive to sound than to meaning.** (Antonyms score 4.55 only because they
differ in *both* — a confounded comparison.)

**M3 — Stage D is a pure bag (composition destroyed):**
| pair | varṇa dist | reading dist |
|---|---|---|
| "the dog bit the man" vs "the man bit the dog" | 0.00 | **0.000** |
| "profit before people" vs "people before profit" | 0.00 | **0.000** |
| "she helped him" vs "he helped her" | 0.44 | **0.000** |

Word order is **completely** discarded — meaning-flipping reorderings give *identical*
readings. The aggregation is so coarse it even collapses lexical differences (she/him vs
he/her → identical).

**M5 — how much is the reading just the phonetic decomposition?**
`corr(varṇa-Jaccard distance, reading distance) = 0.38`. Moderate: Stage C contributes
*some* non-phonetic structure, but the reading is substantially explained by phonetic
overlap and C's signal is too weak to overturn B.

## 2. Information-flow diagram

```
Sentence
  │  (A) English preprocessing: lowercase/strip      — lossless-ish, NOT the cause
  ▼
Graphemes
  │  (B) grapheme→IAST→varṇa decomposition           — ✗ MEANING LOST HERE (sound-bound)
  ▼                                                     synonyms varṇa-dist 0.82 ≈ random 0.84
Varṇa sequence  ──(order present here)
  │  (C) per-varṇa essence/pole lexicon lookup       — weak semantic add (corr 0.38), inherits B
  ▼
Per-varṇa pole/vote stream
  │  (D) aggregate → 5 scalar features (bag)          — ✗ COMPOSITION LOST HERE (order discarded)
  ▼
Final reading ρ  (sound-dominated, order-free)
```

## 3. Failure-localization matrix

| Perturbation | Reacts at B? | Reacts at C? | Reacts at D (reading)? | Should react? | Verdict |
|---|---|---|---|---|---|
| synonym (sound↑, meaning=) | **yes (0.82)** | inherits B | **yes (2.31)** | no | B binds to sound |
| rhyme (sound=, meaning↑) | no | no | **no (0.18)** | yes | meaning invisible |
| word-order (composition↑) | no (0.00) | no | **no (0.000)** | yes | D is a bag |
| antonym (both↑) | yes | yes | yes (4.55) | yes | confounded |
| punctuation/case | no | no | no | no | OK (sanity) |

## 4. Estimated contribution of each stage to the O1.5 failure

| Stage | Role in failure | Est. contribution |
|---|---|---|
| A — English preprocessing | none (clean) | ~5% |
| **B — grapheme→varṇa** | **destroys lexical/paraphrase meaning; binds reading to sound** | **~50%** |
| C — essence/pole lexicon | weak semantic signal, can't compensate; inherits B's sound-binding | ~10% |
| **D — final aggregation** | **destroys composition (bag); collapses lexical differences** | **~35%** |

## 5. Counterfactual analysis

- **If C/D were perfect, could meaning be recovered from B's output?** **No.** B maps
  "happy" and "joyful" to near-disjoint varṇa sets (Jaccard 0.82). The fact that they are
  synonyms is *not present* in the varṇa sequence, so no downstream stage can recover it.
  **The paraphrase failure is fundamentally upstream (B).**
- **If B were perfect, would D still destroy meaning?** **Yes, for composition.** The bag
  aggregation makes "dog bites man" = "man bites dog" regardless of how semantic the
  per-varṇa values are. **The compositional failure is fundamentally downstream (D).**

The two failures are **independent and additive**: fixing one leaves the other.

## 6. Ranked redesign opportunities (ranked only — NOT redesigned)

Ranked by expected gain *against the measured failures*, with difficulty and scientific risk:

| Rank | Candidate | Addresses | Expected gain | Difficulty | Scientific risk |
|---|---|---|---|---|---|
| 1 | **Meaning-bearing input representation** (not sound-derived) | B | **High** — the only thing that fixes paraphrase | Hard | **Very high** (concedes "meaning from phonemes") |
| 2 | CSR / contextual resonance | B (partly) | Potentially high | Hard (neural, infra-blocked) | High |
| 3 | Compositional / multi-word aggregation | D | Medium — fixes word-order only | Moderate | Low |
| 4 | Context-sensitive varṇa interpretation | B (weakly) | Low — doesn't make synonyms converge | Moderate | Medium |
| 5 | Hierarchical composition | D | Low (premature while B broken) | Hard | Medium |
| 6 | Sentence-level normalization | — | Low (no effect on sound-binding) | Easy | Low |

**Key asymmetry:** the dominant failure (B, ~50%) is the one **no cheap redesign fixes** —
sound-derived decomposition cannot represent that different-sounding words share meaning.
The fixable failure (D, compositional aggregation) is real but, alone, still leaves O1.5
failing because B's paraphrase loss remains.

## 6′. Recommendation

Not "redesign preprocessing" (A is clean), not "redesign aggregation alone" (fixes only D,
~35%, leaves the larger B failure), not "redesign reading construction / C" (C is weak but
not the primary cause).

**The next research effort belongs at the input/decomposition layer (Stage B): does
Symbol-U have any meaning-bearing representation at all, or is the varṇa decomposition
inherently a sound code for English?** The measurements say the latter — synonyms are
varṇa-disjoint, sound-alikes collapse, meaning moves the reading 12× less than sound. That
is structural, not a tuning gap.

Adversarially stated: the evidence supports **abandoning the current reading architecture
for the goal of representing the lexical meaning of English text.** The only directions
that could in principle address Stage B are a genuinely meaning-bearing signal (CSR /
contextual resonance), which is hard and infra-blocked — or conceding that "semantic
meaning emerges from English phoneme/varṇa statistics" is the hypothesis that just failed
its cheapest test. Compositional aggregation (Stage D) is worth fixing but is secondary and
insufficient on its own. **Do not invest in policy translation, aggregation polish, or
preprocessing; the meaning is lost before any of those stages run.**
