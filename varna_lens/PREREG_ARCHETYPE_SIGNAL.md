# Pre-registration — Does the varṇa chain recover Sattvic ARCHETYPAL FUNCTION?

> **Status: PRE-REGISTERED (written before results).** Third, independent falsification probe for
> `varna_lens`. The first two tests returned **NO_SIGNAL** (lexical/dictionary meaning recovery,
> `RESULTS_ACOUSTIC_SIGNAL*.md`) and **NO_UTILITY_SIGNAL / INCONCLUSIVE** (non-lexical blind utility,
> `RESULTS_UTILITY_SIGNAL*.md`). Those are accepted and not relitigated. This test asks a **different
> hypothesis** and must clear its own controls before any claim. It is still **not** about C×R×S /
> Conscious Generation, and a positive result here would **not** revive the lexical-meaning claim — it
> would, at most, license a narrow *archetypal-function* claim.

## The missing-middle hypothesis

Prior tests measured the wrong target: **dictionary meaning** ("can the chain identify the word
*doctor*?"). They could not. This test measures **archetypal function** — the deeper *transformation*
a role-word enacts (*doctor* = **suffering → healing**), not its denotation.

Three layers of "meaning" are distinguished:

| layer | guṇa | what it is | prior verdict |
|---|---|---|---|
| 1. lexical | Tamas | dictionary denotation (*doctor* = physician) | NO_SIGNAL (falsified) |
| 2. contextual | Rajas | role-in-a-scene (medical professional acting) | (out of scope here; CSR's domain) |
| 3. **acoustic essence** | **Sattva** | **archetypal transformation** (suffering → healing) | **← this test** |

- **H1 (archetype):** the **real** varṇa chain depicts a word's pre-registered transformation archetype
  better than chains from a **scrambled** lexicon **and** a **random-symbolic** lexicon, judged blind.
- **H0 (no archetype signal):** real ≈ scrambled and/or real ≈ random — any apparent fit is the
  reader/judge rationalizing an arc onto a transformation, not the specific sound→propensity map.

## Design — one archetype, three lexicons, blind fit-scoring

1. **Wordlist** (`wordlist_archetype.py`): N role/function words whose archetypal transformation is
   broadly agreed *from the role*, **authored before any chain is computed** (no fitting archetypes to
   chains). Each entry: `{word, pron, domain, from_state, to_state}`. Example: `doctor → suffering →
   healing`, `teacher → ignorance → understanding`, `judge → dispute → resolution`.
2. **Chain rendering** (`archetype_test.py`): for each word, the lens reading is rendered as a compact,
   **lexicon-agnostic** transformation *arc* (ordered worldly poles, the `−`-coda dissolution arcs
   `worldly ⤳ counter`, and the whole-word essence). The template is **identical** across lexicons;
   only the glosses filling it differ.
3. **Three lexicons (the required controls):**
   - **real** — `lexicon_authoritative.json` (the Sanskrit varṇa map).
   - **scrambled** — the real (worldly, counter) **pairs** permuted among consonant keys, and vowel
     essences permuted among vowel keys (S = 20 seeded scrambles, averaged). **Preserves** the exact
     propensity vocabulary, antonym pairing, +/− structure, gloss multiset, and arc length; randomizes
     **only** which sound carries which propensity. *This is the decisive control for the acoustic
     claim* — real can beat it only if the specific sound→propensity attachment carries the archetype.
   - **random-symbolic** — a lexicon of the same structure built from a **neutral, non-psychological**
     vocabulary pool (concrete/elemental nouns), seeded (S = 20, averaged). Controls for "any
     structured symbolic arc reads as a transformation." A real win over *this* but not over scrambled
     would mean the effect is merely "uses psychological vocabulary," not the acoustic model.
4. **Blind judge — fit scoring (not word-ID).** For each word the judge sees the archetype
   `{from} → {to}` and the **three chains in randomized, hidden order**, and rates how well **each**
   chain depicts that transformation on a **1–5** scale. The judge never sees the word, the lexicon
   identity, or which chain is which. Within-item presentation controls per-archetype difficulty;
   per-word trio order is seed-randomized so no slot favors `real` systematically (balance reported).
   - **Confirmatory: LLM judges** (blind sub-agents) — multiple judges, per-word scores averaged.
   - **Null arm: `random` judge** — scores ignore content → Δ ≈ 0 (sanity check the pipeline).
   - **Deterministic arm: `overlap` judge** — CPU-reproducible token-overlap between chain glosses and
     the archetype words; low-power, reported, non-gating.
   - **Order-shuffled real arm** — real lexicon with phoneme order shuffled, to check the effect (if
     any) needs the *ordered* chain and isn't just the bag of glosses.

## Primary metric & pre-registered verdict

- **fit(real), fit(scrambled), fit(random)** — per-word mean fit (1–5), averaged over judges (LLM arm)
  and over the S seeded control lexicons.
- **Δ_scr = fit(real) − fit(scrambled)** and **Δ_rnd = fit(real) − fit(random)**, each with a 95%
  **bootstrap CI** (10 000 resamples over words).
- **Practical threshold:** `MIN_EFFECT = 0.30` points (1–5 scale), same bar as the utility prereg.

**Verdict rule (computed by the harness, not by hand):**

- **ARCHETYPE_SIGNAL_DETECTED** ⟺ `CI_lower(Δ_scr) > 0` **AND** `CI_lower(Δ_rnd) > 0`
  **AND** `min(Δ_scr, Δ_rnd) ≥ MIN_EFFECT`.
  → real beats **both** controls, decisively and product-meaningfully.
- **ARCHETYPE_SIGNAL_WEAK** ⟺ `CI_lower(Δ_scr) > 0` **AND** `CI_lower(Δ_rnd) > 0` but
  `min(Δ_scr, Δ_rnd) < MIN_EFFECT`. → real beats both with statistical confidence but the effect is
  below the product bar. No product claim; report as a real-but-tiny signal.
- **NO_ARCHETYPE_SIGNAL** ⟺ the CI of `Δ_scr` **or** `Δ_rnd` contains 0 (real fails to clearly beat at
  least one control). This is the user's stated gate: *no detection unless real > scrambled AND real >
  random with CI lower bound > 0.*

The conjunction is required: beating random alone (psychological vocabulary helps) is **not** an
acoustic-model result; only beating **scrambled** isolates the sound→propensity attachment.

## Registered prediction (before running)

Given the lexical NO_SIGNAL and the utility NO_UTILITY_SIGNAL — and that the scramble preserves the
entire propensity vocabulary and arc structure — I predict **NO_ARCHETYPE_SIGNAL**: real may edge out
the *random-symbolic* lexicon (psychological words read as transformations more readily than neutral
nouns), but will **not** clearly beat the *scrambled* lexicon, because the specific sound→propensity
attachment is the thing two prior tests found carries no signal. Recording this so the result can prove
me wrong.

## Interpretation rules (binding)

- **ARCHETYPE_SIGNAL_DETECTED** → a narrow, defensible claim is licensed: *"the real varṇa chain
  depicted pre-registered archetypal transformations measurably better than scrambled and random
  controls in a blind fit test."* **Not** licensed: meaning/dictionary recovery; any C×R×S /
  Conscious-Generation link; calling it "Sattvic truth." Replication (new words, new judges,
  counterbalanced) required before productizing.
- **ARCHETYPE_SIGNAL_WEAK** → interesting, not actionable; treat like the INCONCLUSIVE utility result.
- **NO_ARCHETYPE_SIGNAL** → the Sanskrit acoustic model adds **no measurable Sattvic/archetypal
  signal**; Varṇa Lens remains a consistent symbolic mirror whose value is reader-supplied. The
  `phoneme_overreach` firewall stands.

## Reproducibility

Fixed seeds (`BASE_SEED = 20240624`, S = 20). `python archetype_test.py --judge random` and
`--judge overlap` are CPU-only and deterministic. `--judge llm` is the confirmatory arm (blind
sub-agents / API); its per-word scores are recorded so the verdict is recomputable. Results →
`RESULTS_ARCHETYPE_SIGNAL.md`; verdict computed by the rule above.
