# Varṇa Lens — a personal, methodical word-essence tool

> **What this is:** a disciplined way to abstract a word's "hidden essence" from a **frozen varṇa lexicon**
> under **explicit, fixed acoustic rules**, so you can apply it the same way every time and honestly track
> where it flows and where it strains.
>
> **What this is NOT:** a claim about Sanskrit, a universal truth, or part of the C×R×S engine. C×R×S
> firewalls sound→meaning on purpose; this lives **outside** it, clearly labeled as an interpretive lens.
> It needs no external validation to be a useful personal instrument — its only discipline is *consistency*.

## Falsification record (pre-registered, computed by rule)
Three independent pre-registered blind tests, each with a scrambled-lexicon control:
- **Lexical meaning recovery** → **NO_SIGNAL** (real ≈ chance ≈ scrambled). `PREREG_ACOUSTIC_SIGNAL.md` /
  `RESULTS_ACOUSTIC_SIGNAL*.md`.
- **Non-lexical utility** → **NO_UTILITY_SIGNAL / INCONCLUSIVE** (Δ ≈ 0.07, far below threshold).
  `PREREG_UTILITY_SIGNAL.md` / `RESULTS_UTILITY_SIGNAL*.md`.
- **Archetypal-function fit (the "missing middle")** → **NO_ARCHETYPE_SIGNAL** (real ≈ scrambled;
  both beat only a neutral-noun lexicon — a vocabulary effect, not an acoustic one).
  `PREREG_ARCHETYPE_SIGNAL.md` / `RESULTS_ARCHETYPE_SIGNAL.md` / `archetype_test.py`.

Bottom line: the lens does **not** decode meaning, utility, or archetype from the specific
sound→propensity attachment. Its value is **consistency for reflection**, not truth — and it stays
firewalled from C×R×S (`phoneme_overreach`).

## The frozen lexicon (`lexicon_authoritative.json`)
- **Consonants:** each carries its **worldly (bīja) binding vṛtti** (`negative` field — the propensity the
  sound activates) + a **dissolved/spiritual counter-pole** (`positive` field).
- **Vowels:** each carries a **worldly active essence** (`positive` field) + a **distortion pole**
  (`negative` field).

The lexicon is **frozen**: you never adjust an essence to fit a word after the fact. That's the whole game.

## The one rule — worldly-reference order-polarity (Option 1)
Every varṇa is read by its **worldly propensity** (consonant `negative` field; vowel `positive` field). The
displayed meaning is **always** that worldly pole — the spiritual pole is what you get by **dissolving** it.
Sound order sets only the **sign**:

- **+ AFFIRMED** — consonant has a **vowel after** it *or is word-initial*; vowel has a **consonant before**
  it (anchored). The bīja **activates** the propensity.
- **− DISSOLVING** — consonant is a **coda**; vowel **leads** un-anchored. The structure is **eliminating**
  that worldly propensity (→ spiritual).

Examples: *kāla* = Ka⁺ **Hope** → ā⁺ Expansion → La⁻ **Cruelty** ⟹ [a Birth] ("hope, rebounding as cruelty");
*war* = Va⁺ **Dharma** → o⁺ Closure → Ra⁻ **Annihilation** ("righteous annihilation"); *aim* = ai⁻
Welfare/materialization → Ma⁻ Indulgence (the **m** eliminates the worldly aim). Full rule + worked table in
`RULES.md`.

## Segmentation into acoustic varṇas
- **Default (roman/IAST):** literal tokenization, faithful for transliterated Sanskrit (IAST writes every
  vowel, so *ka* ≠ *ak*).
- **`--g2p` (English):** acoustic breakdown via nltk-cmudict (ARPAbet → varṇa). **Approximate** — English
  phonology ≠ varṇas (e.g. English *T* maps to dental *ta*, not retroflex *ṭa*; override with `--varnas`).
- **`--varnas` (authoritative):** you give the exact acoustic order, e.g. `--varnas "ka,la"` or `"a,k"`.

## Usage
```bash
python varna_lens.py "kāla"                 # roman/IAST
python varna_lens.py "ak"                   # order rule: destroys
python varna_lens.py "time" --g2p           # English acoustic (approximate)
python varna_lens.py --varnas "ka,la"       # exact, authoritative

# predict-then-check log (the honesty record): abstract first, then record the real meaning + verdict
python varna_lens.py "kāla" --log log.csv --actual "time" --verdict flowed
```

## Batch test (the 30-word honest pass)
```bash
# 1. put words (one per line; '#' comments; optional 'word<TAB>actual') in words.txt, then:
python varna_lens.py --batch words.txt --log run1.csv     # prints predictions, leaves verdict BLANK
# 2. open run1.csv, fill the 'verdict' column (flowed/stretched/missed) WITHOUT pre-glancing meanings
python varna_lens.py --tally run1.csv                     # counts + % + honest read

# or do it in one interactive pass (prompts actual + verdict per word):
python varna_lens.py --batch words.txt --interactive --log run1.csv
```
`words_sample.txt` is a starter list. The non-interactive flow is the cleaner test: the tool commits to its
prediction first; you supply the truth and the verdict afterward, so you can't retrofit.

## The one discipline that keeps it honest
**Predict, then check — and log both.** Abstract the essence *before* recalling the real meaning, then
record `flowed / stretched / missed`. Over time the log shows you, without self-deception, where the lens
holds and where it bends. That's the most rigor this kind of inquiry can carry — and it's enough to keep it
real without pretending it's universal.
