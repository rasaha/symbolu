# Varṇa Lens — The Rule (single, order-polarity)

> Interpretive lens — not a universal claim, not part of C×R×S. One frozen lexicon
> (`lexicon_authoritative.json`), one rule, applied identically every time.

## The one rule (order-polarity)
Each varṇa (consonant **or** vowel) gets **one pole**, decided purely by sound order:

- **Consonant** → **POSITIVE** if a **vowel follows** it; **NEGATIVE** if not (a coda, no vowel of its own).
- **Vowel** → **POSITIVE** if a **consonant precedes** it; **NEGATIVE** if not (word-initial / leads).

(A consonant looks **forward** for its vowel; a vowel looks **backward** for its consonant — mirror images,
"and vice versa".)

The chosen pole supplies the meaning:
- consonant + → its **positive vṛtti** · consonant − → its **negative vṛtti**
- vowel + → its **positive essence** · vowel − → its **negative essence**

The word essence = every varṇa, in order, with its chosen pole.

### Worked examples
| word | reading |
|---|---|
| **love** (l·o·v·e) | La⁺ Compassion → o⁺ Closure → Va⁺ Truth → e⁺ Practical thought |
| **war** (w·a·r) | Va⁺ Truth → a⁺ Birth of cognition → Ra⁻ **Annihilation** |
| **ak** (a·k) | a⁻ restless-starting → Ka⁻ **Hope** (both negative) |
| **ka** (k·a) | Ka⁺ Detachment → a⁺ Birth of cognition (both positive) |
| **kāla** | Ka⁺ Detachment → ā⁺ Expansion → La⁺ Compassion → a⁺ Birth of cognition |

## Segmentation (how a word → varṇas)
- **Sanskrit / romanized (default):** literal, left to right, **no inherent "a" added** (so `ka` ≠ `ak`).
  Aspirates/retroflex/sibilants are single units (kh, gh, ṭh, ḍh, ś, ṣ, ṅ, ñ, ṇ, kṣ …).
- **English (`--g2p`):** via cmudict (approximate — e.g. English *t* → dental *ta*; override with `--varnas`).
- **Manual (`--varnas`):** you give the exact varṇas, e.g. `va,a,ra`.

## What's FIXED vs a CHOICE
- **Fixed:** the lexicon (each letter's two poles + vowel essences), the segmentation, and the rule above.
- **Choice (only):** how to break a word into sounds when ambiguous (use `--varnas` to pin it).

There is now **one** pole rule and **no** position/stance/pair knobs.

## Run
```bash
python varna_lens.py "love"            # the rule (default)
python varna_lens.py "war"
python varna_lens.py --varnas "va,a,ra"   # pin the exact varṇas
python varna_lens.py "time" --g2p         # English (approximate)
```
*(legacy experiments still reachable: `--pairs`, `--db`, `--reverse`, `--vp-consonly` — not the rule.)*
