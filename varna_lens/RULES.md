# Varṇa Lens — The Rule (single, order-polarity)

> Interpretive lens — not a universal claim, not part of C×R×S. One frozen lexicon
> (`lexicon_authoritative.json`), one rule, applied identically every time.

## The one rule (order-polarity)
Each varṇa (consonant **or** vowel) gets **one pole**, decided purely by sound order:

- **Consonant** → **POSITIVE** if a **vowel follows** it **or it is word-initial** (no vowel before it);
  **NEGATIVE** otherwise (a coda with a vowel before it and none after).
- **Vowel** → **POSITIVE** if a **consonant precedes** it; **NEGATIVE** if not (word-initial / leads).

(Word-initial consonants are always positive — so the final-vowel rule never flips a *leading* consonant
to a coda. e.g. *the* = Ḍa⁺ Fearlessness ⟹ [a creation].)

(A consonant looks **forward** for its vowel; a vowel looks **backward** for its consonant — mirror images,
"and vice versa".)

**Final-vowel rule:** a vowel at the **end** of the word is **removed from the stitched chain** and reported
separately as the **whole-word essence** (it summarizes the word). Removing it turns the **preceding
consonant into a coda → negative.** (e.g. *lobha* → drop final *a* → *bh* becomes a coda → "deluded
obsession"; the dropped *a* = the word's summary essence.)

The chosen pole supplies the meaning:
- consonant + → its **positive vṛtti** · consonant − → its **negative vṛtti**
- vowel + → its **positive essence** · vowel − → its **negative essence**

The word essence = every remaining varṇa, in order, with its chosen pole **⟹ [whole-word essence]**.

### Worked examples
| word | reading | whole-word essence (final vowel) |
|---|---|---|
| **lobha** | La⁺ Compassion → o⁺ Closure → **Bha⁻ Deluded obsession** | a⁺ Birth/creation |
| **love** | La⁺ Compassion → o⁺ Closure → **Va⁻ Dharma (righteousness outside)** | e⁺ Practical thought |
| **kāla** | Ka⁺ Detachment → ā⁺ Expansion → **La⁻ Cruelty** | a⁺ Birth |
| **war** | Va⁺ Truth → a⁺ Birth → **Ra⁻ Annihilation** | — (ends in consonant) |
| **ak** | a⁻ restless-starting → Ka⁻ **Hope** (both negative) | — |

## Segmentation (how a word → varṇas) — **AUTO by default**
You must read the **sounds**, not the spelling. So the lens auto-routes:
- **Has IAST diacritics** (ā, ī, ṛ, ṅ, ṭ, ḍ, ś, ṣ …) → **literal** Sanskrit reading (the letters *are* the sounds).
- **A real dictionary word** (English/other) → **g2p**: word → pronunciation → varṇas
  (e.g. *phone* → F OW N → Pha·o·Na; *knee* → N IY → Na·ī; *the* → DH AH → Ḍa·a).
- **Otherwise** → literal fallback.

English↔Sanskrit sound notes: English **f** = **Pha** (p stays Pa); English voiced **th** (the/this) = **Ḍa**.
Overrides: `--g2p` force pronunciation · `--roman` force literal · `--varnas "va,a,ra"` pin exact varṇas.

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
