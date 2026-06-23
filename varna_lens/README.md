# Varṇa Lens — a personal, methodical word-essence tool

> **What this is:** a disciplined way to abstract a word's "hidden essence" from a **frozen varṇa lexicon**
> under **explicit, fixed acoustic rules**, so you can apply it the same way every time and honestly track
> where it flows and where it strains.
>
> **What this is NOT:** a claim about Sanskrit, a universal truth, or part of the C×R×S engine. C×R×S
> firewalls sound→meaning on purpose; this lives **outside** it, clearly labeled as an interpretive lens.
> It needs no external validation to be a useful personal instrument — its only discipline is *consistency*.

## The frozen lexicon (`lexicon.json`)
- **Consonants:** each carries a *leading binding vṛtti* (the manifest essence) + a *liberating
  counter-pole*. From your `Sanskrit_Varna_Mala.pdf`.
- **Vowels:** each is a *layer-bridge* (Body → Identity → … → Brahman) with a positive and shadow pole.
  From your `Sanskrit_letters.docx` + the PDF.

The lexicon is **frozen**: you never adjust an essence to fit a word after the fact. That's the whole game.

## The fixed rules
- **R1 — Order / polarity.** A consonant **followed by a vowel** (C→V, e.g. *ka*) **CREATES** its vṛtti (+).
  A consonant **not** followed by a vowel (e.g. *ak*, coda) **DESTROYS / negates** it (−).
- **R2 — Position (two-consonant word).** The **1st** consonant exerts a **positive / forward** influence;
  the **2nd** exerts a **negative / reactive** influence (rebounding on the first).
- *kāla* = Ka(+Āśā, forward) → La(+Krūratā, reactive) = "hope projected, rebounds as cruelty."
- *ak* = k destroyed = "hope destroyed."
- (>2 consonants: only R1 is applied as a provisional chain — give the >2 position rule to finalize R2.)

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

## The one discipline that keeps it honest
**Predict, then check — and log both.** Abstract the essence *before* recalling the real meaning, then
record `flowed / stretched / missed`. Over time the log shows you, without self-deception, where the lens
holds and where it bends. That's the most rigor this kind of inquiry can carry — and it's enough to keep it
real without pretending it's universal.
