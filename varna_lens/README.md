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
Every varṇa has two **states of expression** — not moral poles, and **never** chosen from any external
label about the referent (good/bad, useful/useless, auspicious/inauspicious). The only question the
framework asks of an acoustic tendency is whether it **binds** consciousness or **releases** it:
- **`binding_state`** — worldly, contractive, attachment-forming, bondage-producing (the bīja propensity
  the sound activates).
- **`liberating_state`** — sublimated, unbinding, expansive, dharma/mokṣa-oriented (its dissolved counter).
- For a **consonant** the worldly default is its `binding_state`; for a **vowel** the worldly active
  essence sits in its `liberating_state` field (an intentional field asymmetry).

The lexicon is **frozen**: you never adjust an essence to fit a word after the fact. That's the whole game.

## The one rule — worldly-reference order-polarity (Option 1)
Every varṇa is read by its **worldly propensity** (consonant `binding_state`; vowel `liberating_state`). The
displayed meaning is **always** that worldly state — the liberating state is what you get by **dissolving**
it. Sound order sets only the **sign** — never a semantic judgment about the word:

- **+ AFFIRMED** — consonant has a **vowel after** it *or is word-initial*; vowel has a **consonant before**
  it (anchored). The bīja **activates** the propensity.
- **− DISSOLVING** — consonant is a **coda**; vowel **leads** un-anchored. The structure is **eliminating**
  that worldly propensity (→ spiritual).

Examples: *kāla* = Ka⁺ **Hope** → ā⁺ Expansion → La⁻ **Cruelty** ⟹ [a Birth] ("hope, rebounding as cruelty");
*war* = Va⁺ **Dharma** → o⁺ Closure → Ra⁻ **Annihilation** ("righteous annihilation"); *aim* = ai⁻
Welfare/materialization → Ma⁻ Indulgence (the **m** eliminates the worldly aim). Full rule + worked table in
`RULES.md`.

## Emergent valence (derived, never supplied)
A whole word is **never** stamped binding or liberating from a judgment about what it denotes. Instead the
chain is decoded first, then summarised: `emergent_valence.lean` ∈ `binding | liberating | mixed` is the
majority of the per-varṇa signs the structure already produced (its `basis` records the vote counts and
states it is *derived from the chain, not supplied from semantic labels*). So *river* reads
**liberating** and *kill* reads **binding** because of their **sounds**, not because anyone called a river
good or killing bad — and *poison* reads **liberating**, exactly the point: the lens does not moralise.
Proven structurally by `ontology_test.py`.

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
