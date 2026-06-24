# Varṇa Lens — Concept Brief

## 1. The concept

**Varṇa Lens** abstracts a word's "hidden essence" by reading its **sounds** through a frozen lexicon of
Sanskrit varṇa (acoustic-root / bīja-akṣara) **mental propensities**. Each sound carries a psychological
propensity (e.g. *Hope*, *Cruelty*, *Discrimination*, *Awakening*) with a worldly pole and a spiritual
counter-pole. A word becomes an ordered chain of these propensities.

The claim is deliberately **not** about a word's physical or dictionary meaning. It is a **parallel symbolic
layer** — a *mental-propensity* reading of a word, distinct from what the word denotes. In the project's own
honest framing: it is **"an esoteric system — astrology for language"** — a consistent, deterministic symbolic
mirror, not a decoder of truth.

## 2. Rules applied (current implemented rule set)

1. **Segmentation — sound first, not spelling.** English → g2p (pronunciation); other languages → native
   phonetics mapped to varṇas; Sanskrit/IAST → literal (its letters *are* its sounds). Sound notes:
   `f`=Pha, voiced *th*=Ḍa, /ʌ/ ("cut")=a; retroflex (Ṭa-varga: ṭ ḍ ṇ, or ITRANS caps T D N) vs dental
   (ta-varga); `sh`=Śa / `Sh`=Ṣa; `q`=Ka.
2. **Vowel-attachment polarity (the core rule).** Each consonant: a **vowel immediately follows** it (onset)
   → its **spiritual pole (+)**; **bare** — no vowel after it (word-final, or before another consonant) → its
   **worldly pole (−)**; the **word's first consonant** → **worldly (−)**, the leading seed. (So *art* kala →
   La⁺ Compassion; *time* kaal → La⁻ Cruelty; the same La flips on whether a vowel attaches.)
3. **Doubled consonant.** Two of the same in a row (kill *ll*, happy *pp*): **1st → spiritual (+)**, **2nd →
   worldly (−)**. (Note: this fires only when both occurrences survive segmentation — i.e. letter-based,
   IAST, or pinned `--varnas` input. The default English **g2p collapses geminates to one sound** (*kill* →
   K IH1 L, a single /l/), so the doubled rule does not apply to English words read by pronunciation.)
4. **Vowels.** A vowel takes its active essence; **+** when a consonant precedes it, **−** when it leads.
5. **Dissolution.** A **−** (worldly) consonant prints its worldly pole **⤳ its spiritual counter** (e.g.
   *the* = Ḍa⁻ Shyness ⤳ Fearlessness).
6. **Final vowel = whole-word essence** (reported as the word's summary; it still counts as the vowel that
   follows the preceding consonant, so that consonant stays an onset → spiritual).

*Explored variants (discussed, not the default):* letter-based English; syllable-group reset; cluster-
clubbing (vowel-less clustered consonant → spiritual — the immediate predecessor, superseded by vowel-
attachment); sign-selects-which-pole. The lexicon was also corrected for Sanskrit acoustic-root source
fidelity on 8 letters (Ca, Ja, Ma, Ra, Va, Śa, Ṣa, Sa).

*Known segmentation scope:* input is read as **sound** — IAST diacritics (`kāla`), English/other dictionary
words via g2p, and a roman literal fallback. **Raw Devanāgarī script is not segmented** (use IAST/romanized
forms, e.g. `kala`/`kāla`, or pin with `--varnas`).

## 3. Project stage

**Built & frozen.** The lens engine (`varna_lens.py`), the authoritative lexicon, the rules, and full docs
exist and run deterministically.

**Falsified (the honest core).** Pre-registered blind tests were run — twice on the lexical/meaning question
(original + source-corrected lexicon), once on a letter-based-English variant, and once on non-lexical
*utility* (real vs scrambled artifacts). Every result:

| test | verdict |
|---|---|
| lexical meaning recovery (orig + corrected + letter-English) | **NO_SIGNAL** (real ≈ chance, not above scrambled) |
| non-lexical utility (real vs scrambled, blind judges) | **NO_UTILITY_SIGNAL / INCONCLUSIVE** (Δ ≈ 0.07, far below threshold) |

**Conclusion (settled).** The lexicon does **not** decode meaning and carries **no shared signal** beyond
being a *consistent* symbolic system. Apparent aptness is reader-supplied (the same word's sounds read as
bliss or misery depending on poles chosen; a scrambled lexicon reads about as aptly). It is therefore a
**contemplative / consistent-contrast instrument**, firewalled from C×R×S / Conscious Generation
(`phoneme_overreach` taboo).

**Not built.** The product/application layer (designed in `STRATEGY_POST_FALSIFICATION.md`, not implemented).

## 4. What tool can be built — as far as LLM generation is concerned

The honest architecture is **LLM generation *on top of* the deterministic lens — never the lens feeding
*into* an LLM as a meaning/score signal.**

```
word ──► [DETERMINISTIC LENS]  ──► consistent propensity scaffold ──► [LLM AUTHORING] ──► reading
         (frozen, reproducible)     (the same word → same chain)       (fluent, personal, coherent)
```

- **The lens supplies what an LLM lacks:** a *fixed, reproducible, ownable* symbolic scaffold. The same word
  always yields the same chain — so it's a stable mirror you can return to, not a fresh hallucination each
  prompt. That determinism is the moat over "just ask an LLM to reflect on a word."
- **The LLM supplies what the lens lacks:** Stage-2 **coherence** — turning a terse propensity chain into
  fluent, evocative, context-aware reflection. (This is exactly what LLMs do effortlessly; it's *authored*
  coherence, not decoded truth.)

**Buildable tools (all generative, all honest):**

1. **Reflection / journaling companion** — word → scaffold → LLM-authored reflection questions + a journaling
   prompt. Daily, personal, repeatable. (The core loop.)
2. **Naming / branding decision aid** — candidate names → consistent propensity palettes → LLM-authored mood
   descriptions + an **A/B/C contrast** for choosing. This is the *"which fits the situation — hat or cap?"*
   use: a **consistent tie-breaker** for choice. Useful because it's consistent, not because it's true.
3. **Creative-seed generator** — word/name → scaffold → LLM riffs imagery, character, place, or story seeds.

**The single honesty contract (what keeps it a tool and not a fraud):**
- The scaffold is **deterministic**; the reading is **LLM-authored**.
- Always presented as a **crafted reflection / consistent contrast**, never as the word's *decoded meaning*.
- Never wired into C×R×S / Conscious Generation as a feature, prior, score, or retrieval key.

**What it is NOT, for LLM generation:** not a meaning decoder, not a semantic signal, not a quality/scoring
feature, and not a place where established sound-symbolism heuristics add value (an LLM already internalizes
those). Its only contribution to generation is as a **consistent symbolic seed/scaffold the LLM elaborates** —
valued for consistency and reflection, not for truth.
