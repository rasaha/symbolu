# Symbol-U Input → Varṇa Bridge — Design Spec **V0 (DRAFT)**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: DRAFT_FOR_REVIEW — open maintainer decisions marked ▶. No experiment, no scoring, no mapping/parser/gloss
change. This is the prerequisite spec for a *future* utility test; it does NOT reopen or modify B1.12.**

## 0. Why this exists

B1.12 is closed. Its synthesis showed the varṇa **mappings** are internally patterned but the **strength judgments**
are evaluator-dependent — so more resonance scoring has low value, and the proposed next step is a **utility test**:
does a symbolic-reflection layer make an assistant's answer better than a matched control? That test presupposes a
mechanism that **does not yet exist**: the mappings are defined over **Sanskrit varṇas**, but assistant inputs are
arbitrary (usually English) utterances with no varṇas. This document specifies that missing bridge and, more
importantly, forces the question **"what is the symbolic layer, operationally?"** — because different answers test
different claims.

## 1. The core problem

A frozen mapping like `k → āśā (grasping hope)` is anchored to a Sanskrit phoneme. To act on *"I need more money,"*
something must connect that English utterance to varṇas. There is no natural such connection — so the bridge is an
**engineered, and therefore contestable, construct**. The spec's honesty depends on stating exactly what is assumed
at each step and where new degrees of freedom enter.

## 2. The fork that decides which claim you test ▶ **DECISION 1**

There are two very different "symbolic layers," and they validate different hypotheses:

| Layer | What it uses | What a positive utility result would support |
|---|---|---|
| **(P) Phonological** | user concern → Sanskrit word → **varṇas** → mappings | the actual Symbol-U claim: *phoneme-level* meaning adds value |
| **(O) Ontological** | user concern → **vṛtti/affliction taxonomy** (the mapping *glosses*, used directly) | only that an *affliction-ontology reflection* helps — no phoneme claim |

The mapping glosses (`kāma`/desire, `lobha`/greed, `moha`/delusion, `ahaṃkāra`/ego, …) are already a compact
affliction ontology. Layer **(O)** uses that ontology directly and **never needs varṇas** — it is deployable now and
honest, but it does **not** test Symbol-U's phonological core. Layer **(P)** routes through varṇas and *does* test the
core, but adds a lossy concern→word step.

**Recommendation:** build **(P)** as the experimental arm **and** treat **(O)** as the *critical internal control*
(see §6). The gap **(P) − (O)** is the only thing that isolates whether the **phonological mapping adds anything over
just using the affliction taxonomy**. This is a sharper control than a generic-reflection baseline alone.

## 3. Three candidate bridge mechanisms (feasibility)

| Mechanism | How | Degrees of freedom / risk | Verdict |
|---|---|---|---|
| **A. Concept-word anchoring** | extract concern → look up an *attested Sanskrit word* for it → parse that word to varṇas | the concern→word choice is many-to-one and lossy; if an LLM picks the word freely, evaluator-dependence returns at word selection | **recommended for (P)** — keeps varṇas over *real Sanskrit words* (where B1.12 validated them), IF the concern→word step is a **frozen table**, not free generation |
| **B. Phonetic transliteration of the English word** | money → /ˈmʌni/ → force-fit to varṇas | English phonemes don't map cleanly to Sanskrit varṇas; asserts sound-meaning for *English* sounds — a far larger, untested claim than B1.12 made | **rejected** — out of validated scope, weakest defensibility |
| **C. Direct vṛtti classification** | classify the concern into the affliction taxonomy directly | bypasses varṇas entirely | **this IS layer (O)** — use as the control, not the experimental arm |

So: **(P) = Mechanism A**, **(O) = Mechanism C**, **B is rejected.**

## 4. Pipeline spec for Mechanism A (layer P)

```
user turn
  │
  ▼  [S1] Concern extraction        ── LLM step (variable) ── output: 1–3 concern tags from a FROZEN tag vocabulary
  ▼  [S2] Concern → Sanskrit word   ── FROZEN TABLE lookup (deterministic) ── e.g. money-security→{artha}, craving→{kāma}, anger→{krodha}
  ▼  [S3] Parse word → varṇas       ── frozen sanskrit_stage1_parser.py (deterministic)
  ▼  [S4] Varṇa → mapping glosses   ── frozen varna_native_stage1_merged_v3.json (deterministic)
  ▼  [S5] Reflection synthesis      ── LLM step (variable) ── turns the gloss set into ≤2 sentences of reflection
  ▼
reflection injected into the assistant's context (auxiliary, non-authoritative)
```

**Design rules (frozen for a run):**
- **S2 is a frozen table, not free LLM choice.** This is the single most important constraint: if the model picks the
  Sanskrit word ad hoc, the whole layer inherits the word-selection variance B1.12 already showed is unstable. The
  table maps a *closed* concern-tag vocabulary to attested words; it is version-hashed like any frozen artifact.
- **S1 and S5 are held IDENTICAL across all experiment arms.** Only the *injected content* differs (P-mappings vs
  O-ontology vs generic vs none), so any answer-quality difference is attributable to the injected content, not to the
  extra prompt scaffolding.
- **Determinism where possible:** S2–S4 are fully deterministic and inspectable; S1/S5 use fixed decoding + seed and
  are logged verbatim.
- **Graceful abstention (the `no_relationship` analogue).** If S1 yields no in-vocabulary tag, or S2 has no table
  entry, the layer emits **`NO_APPLICABLE_MAPPING`** and injects nothing. B1.12 showed the instrument's most reliable
  signal is honestly saying "this does not apply" — the bridge must preserve that. Silent forcing is prohibited.
- **Tier-gating from B1.12 (optional ▶ DECISION 2).** The synthesis found only `opposition`/`no_relationship` and
  mappings **d, s, v, y** are agreement-stable. S5 may be restricted to surface reflections grounded in Tier-1
  mappings/relationships first, marking others low-confidence. This keeps the first deployment on the trustworthy
  subset rather than the noisy `implication`/`characteristic_expression` families.

## 5. Interface contract (so the utility test can consume it)

```
bridge(user_turn) -> {
  "status": "OK" | "NO_APPLICABLE_MAPPING",
  "concern_tags": [...],                # S1, from frozen vocab
  "sanskrit_word": "artha" | null,      # S2, from frozen table
  "varnas": ["a","r","th","a"] | [],    # S3
  "mapping_glosses": [{varna, gloss}],  # S4, frozen
  "reflection": "<=2 sentences" | null, # S5
  "tier": "TIER1" | "MIXED" | null,     # S5 confidence per §4 gating
  "provenance": {table_sha, lexicon_sha, parser_sha, seed}
}
```
Everything is inspectable; nothing is asserted as true — the reflection is an **auxiliary, non-authoritative** hint.

## 6. How this feeds the utility test (four arms, not three)

ChatGPT proposed base vs base+symbolic vs base+generic-reflection. Add the ontology arm so the phonological
contribution is isolable:

1. **Base** — assistant alone.
2. **Base + generic reflection** — matched length/structure, no symbolic content (controls for "any second pass").
3. **Base + ontology (O)** — reflection from the vṛtti taxonomy directly, **no varṇas** (controls for "affliction
   framing helps").
4. **Base + phonological (P)** — the full bridge (S1–S5).

Ordered contrasts: **2−1** = does reflection help at all; **3−2** = does affliction framing beat generic; **4−3** =
**does the varṇa layer add anything over the ontology** (the actual Symbol-U question). Blind, randomized-order
judging; heavily weight the "avoided unsupported overinterpretation" axis; include human raters if feasible — else the
usefulness-judge just relocates the evaluator-dependence B1.12 exposed.

## 7. What this spec deliberately does NOT do
- Does not modify the frozen mappings, parser, glosses, scale, taxonomy, or any B1.12 artifact; does not reopen B1.12.
- Does not perform scoring or run any model.
- Does not assert Symbol-U is true; the reflection layer is auxiliary and abstains when nothing applies.
- Mechanism B (English phonetic transliteration) is rejected as out of validated scope.

## 8. Open maintainer decisions before any build
- ▶ **DECISION 1** — layers to build: (P)+(O) as recommended, or (O)-only (deployable now, no phoneme claim), or (P)-only.
- ▶ **DECISION 2** — Tier-gating: restrict first deployment to B1.12 Tier-1 families (d/s/v/y, opposition/no_relationship), or allow all.
- ▶ **DECISION 3** — the S2 concern→word table: its concern-tag vocabulary and word choices must be authored and
  frozen (this is the layer's main new degree of freedom and deserves the same firewall discipline as a word list).
- ▶ **DECISION 4** — judging: LLM-only vs LLM+human for the utility test (bears directly on whether the test escapes
  the evaluator-dependence problem).

## 9. Honest assessment
The bridge is buildable, but it **introduces the concern→word choice as a new, load-bearing degree of freedom** — the
same class of problem (who chooses, and does the choice drive the output?) that made B1.12's scoring evaluator-
dependent. Freezing S2 as a table contains it. The single most valuable thing this architecture buys is the **(P)−(O)
contrast**: it can finally tell whether the *phonological* mapping does any work beyond the affliction ontology it
encodes — which no resonance-scoring run could answer. If (P) does not beat (O), the useful product is the ontology,
not the varṇas; if it does, that is the first evidence for the phonological core that isn't purely an
agreement-between-judges artifact.
