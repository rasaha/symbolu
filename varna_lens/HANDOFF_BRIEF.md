# Varṇa Lens — handoff brief (for an external collaborator)

A personal, interpretive tool that abstracts a word's "hidden essence" from a frozen lexicon of Sanskrit
varṇa (acoustic-root / bīja-akṣara) meanings. **Explicitly NOT a universal claim; deliberately OUTSIDE the
C×R×S engine** (which firewalls sound→meaning). One frozen lexicon, fixed rules, applied identically every
time. Files: `RULES.md`, `LEXICON.md`, `lexicon_authoritative.json`, `varna_lens.py`; falsification in
`PREREG_ACOUSTIC_SIGNAL.md` + `signal_test.py` + `RESULTS_ACOUSTIC_SIGNAL.md`.

## A. THE RULES

**1. Sound, not spelling (segmentation).** Read a word by its *native pronunciation*, not its letters.
- English → g2p (ARPAbet). Key maps: /ʌ/ ("cut") → **a** (अ, not u); voiced *th* ("the") → **Ḍa**
  (retroflex); *f* → **Pha**.
- Sanskrit/IAST → literal (every vowel is written).
- Other languages → pin the true phonetics. Same letter ≠ same sound across languages (pinyin `q` =
  /tɕʰ/ ≈ *ch*, **not** k).
- Retroflex Ṭa-varga (ṭ ṭh ḍ ḍh ṇ) vs dental ta-varga (t th d dh n) written distinctly: diacritics, **or**
  ITRANS capitals `T Th D Dh N` (retroflex) vs lowercase (dental); `sh`=Śa, `Sh`=Ṣa.

**2. Worldly reference (which pole shows).** Every varṇa is read by its **worldly (bīja) propensity**.
Consonant worldly = its *binding* pole; vowel worldly = its *active* pole. The displayed meaning is
**always** worldly. The spiritual pole is what you reach by *dissolving* it (not printed as its own word).

**3. Polarity (the sign).** Set purely by sound-order:
- **First sound of the word is always `−`** (vowel or consonant) — a bare, un-anchored seed.
- A **consonant** is `+` (affirmed) iff a vowel follows it **and** it isn't first; else `−` (coda/leading).
- A **vowel** is `+` iff a consonant precedes it; else `−`.
- `+` = the bīja **activates** the worldly propensity; `−` = it **dissolves** (toward spiritual).

**4. Dissolution target.** A `−` consonant prints `worldly ⤳ spiritual-counter`
(e.g. `the` = Ḍa⁻ Shyness ⤳ Fearlessness).

**5. Final vowel = whole-word essence.** A word-final vowel is removed from the stitched chain and reported
separately as the word's summary (this turns the preceding consonant into a coda).

*Example:* kāla → −Hope⤳Detachment · +Expansion · −Cruelty⤳Compassion ⟹ [Birth].

## B. THE LEXICON (frozen)
~46 varṇas (consonants + 12 vowels). Each has two poles: **positive** (liberating/spiritual) and
**negative** (binding/worldly). For consonants the worldly pole = the negative field; for vowels the worldly
pole = the positive field (intentional asymmetry). Never edited to fit a word after the fact — that's the
whole discipline.

## C. WHAT WE TESTED & FOUND (decisive)
Pre-registered **blind falsification**: mechanical essence (no human) → blind judge picks the true meaning
among 5 valence-matched distractors → repeated on a **scrambled-lexicon** control. 127 words (73 Sanskrit,
36 English, 18 cross-lingual).
- **NO_SIGNAL.** acc(real) = **0.205** ≈ chance (0.20); acc(scrambled) = 0.260; Δ = −0.055
  (95% CI −0.142 … +0.031, straddles 0). **Scrambling the sound→meaning map changed nothing.** Even
  Sanskrit (home turf) was at chance.
- **Conclusion:** the lens does **not** decode meaning. Apparent coherence in use is *interpreter-supplied*
  (pronunciation choice + narrative fit), consistent with same-sound→same-essence and valence-matching seen
  in manual testing. It stays a **contemplative instrument, firewalled from conscious generation** (feeding
  it in = the `phoneme_overreach` taboo).

## D. OPEN STRATEGY QUESTIONS (for the collaborator)
Given a clean NO_SIGNAL, what's the honest, useful path? Candidates to pressure-test:
1. **Reframe as generative, not veridical** — a structured *creativity / meditation prompt* (value = the
   contemplative act, not truth). Is there a real use-case there?
2. **Narrow the hypothesis** — test only where sound↔meaning is *plausibly* real (sound-symbolism /
   phonaesthemes like English *gl-* "light", *sn-* "nose"; ideophones; within one language), instead of
   universal varṇa claims.
3. **Decouple from CG entirely** — keep it personal; spend C×R×S effort elsewhere.
4. **If anyone wants to revive H1** — the only thing that counts is real ≫ scrambled on a blind test (the
   bar it just failed), then a generation ablation vs. a scrambled-essence control.

> Reproduce: `python varna_lens/signal_test.py --judge random` (null → chance, Δ=0);
> `--judge wordnet|llm` for the semantic arms (needs corpus/API). Verdict is computed by the
> pre-registered rule, not by hand.

## Changelog — lexicon source correction (after the NO_SIGNAL test)
Several varṇa entries were later corrected for Sanskrit acoustic-root source fidelity: **Ca, Ja, Ma, Ra, Va,
Śa, Ṣa, Sa** (see each entry's `source_vritti` / `source_notes` in `lexicon_authoritative.json`, and the
"Source fidelity" note in `LEXICON.md`). Notable: Ra's *agnitattva/fire* moved to the vitality (positive)
pole; Va's worldly pole is now *Adharma* (Dharma is the positive/sustaining pole); Ja's worldly pole is
*ahaṁkāra* (ego), not *dambha*.

**Important:** the **NO_SIGNAL** result in `RESULTS_ACOUSTIC_SIGNAL.md` (and the INCONCLUSIVE utility result
in `RESULTS_UTILITY_SIGNAL.md`) were produced on the **prior, pre-correction lexicon**. Any claim about the
**corrected, source-aligned lexicon** requires **re-running the pre-registered tests**. The prior null
result must **not** be used as proof against the corrected lexicon — nor as proof *for* it. Until a re-run,
no signal/utility claim attaches to the corrected lexicon either way.

**Corrected-lexicon re-run completed on `38e38d3`** (same harness/thresholds/wordlists/judges/templates):
- acoustic → **NO_SIGNAL** (acc real 0.173 ≈ chance; Δ = −0.106, CI −0.185…−0.028 — real *below* scrambled)
  → `RESULTS_ACOUSTIC_SIGNAL_CORRECTED_LEXICON.md`
- utility → **NO_UTILITY_SIGNAL** (Δ = +0.067, CI −0.007…+0.140; far below MIN_EFFECT 0.30; position-biased)
  → `RESULTS_UTILITY_SIGNAL_CORRECTED_LEXICON.md`

Prior pre-correction results remain archived and must not be merged with corrected-lexicon results. Bottom
line: the corrected lexicon improved source fidelity but produced **no measurable acoustic or utility
signal** — empirical signal remains unproven on either lexicon version.
