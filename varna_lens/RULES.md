# Varṇa Lens — The Rule (single, vowel-attachment polarity)

> Interpretive lens — not a universal claim, not part of C×R×S. One frozen lexicon
> (`lexicon_authoritative.json`), one rule, applied identically every time.

## The reference: each letter's two poles
Every consonant has two poles in the lexicon: a **worldly** (binding) vṛtti and a **spiritual** (liberating)
counter — Ka = *Āśā* (Hope) ↔ *Nirāśā* (Detachment); La = *Krūratā* (Cruelty) ↔ *Karuṇā* (Compassion); … A
vowel has one **active essence** — a = *Birth of cognition*, ā = *Expansion*, o = *Closure*, …

## The one rule (vowel-attachment polarity)
Each **consonant** takes its pole from whether a **vowel attaches** to it:

- **Onset** — a **vowel immediately follows** the consonant (CV) → its **spiritual (counter) pole (+)**.
- **Bare** — **no vowel after** it (word-final, or before another consonant) → its **worldly pole (−)**.
- The **word's first consonant** → its **worldly pole (−)** (the leading seed) — e.g. Ka = *Hope*.
- A **−** (worldly) consonant is shown easing into its spiritual counter: `worldly ⤳ counter`.

This is why **art ≈ compassion** and **time ≈ cruelty**: in *kala* (कला, art) the `la` has a vowel → La⁺
**Compassion**; in *kaal* (काल, time, schwa-dropped) the final `L` is bare → La⁻ **Cruelty**.

(**Doubled consonant** — *happy* pp, *kill* ll: the **1st** occurrence → **spiritual (+)**, the **2nd** →
**worldly (−)**. e.g. *kill* = … La⁺ **Compassion** → La⁻ **Cruelty**.)

(**Vowels:** a vowel takes its active essence; **+** when a consonant precedes it, **−** when it leads.)

**Final-vowel rule:** a vowel at the **end** of the word is reported separately as the **whole-word essence**
(⟹ […]) and removed from the stitched chain — **but it still counts as the vowel that follows the preceding
consonant**, so that consonant stays an *onset* (→ spiritual), not a coda. e.g. *kala* → … La⁺ **Compassion**
⟹ [a⁺ Birth]; the dropped *a* is the summary essence.

### Worked examples (vowel-attachment)
| word | reading | whole-word essence |
|---|---|---|
| **kaal** (time) | Ka⁻ **Hope** (first) → ā Expansion → **La⁻ Cruelty** (bare) | — (ends in consonant) |
| **kala** (art) | Ka⁻ **Hope** (first) → a Birth → **La⁺ Compassion** (onset) | a⁺ Birth |
| **kāla** | Ka⁻ **Hope** (first) → ā Expansion → **La⁺ Compassion** (onset) | a⁺ Birth |
| **war** | Va⁻ **Adharma** (first) → a Birth → **Ra⁻ Annihilation** (bare) | — |
| **the** | Ḍa⁻ **Shyness** (first) | a⁺ Birth |
| **kill** | Ka⁻ Hope (first) → i I-ness → **La⁺ Compassion** (1st) → **La⁻ Cruelty** (2nd) | — |

(The driver is the **vowel**: the *same* consonant reads spiritual when a vowel attaches to it and worldly
when it is left bare — La⁺ Compassion in *kala* vs La⁻ Cruelty in *kaal*.)

> **Discrepancy noted (Option 1 supersedes an earlier note):** under worldly reference *the* = Ḍa =
> **Lajjā / Shyness** (Ḍa's worldly pole), **not** *Fearlessness*. Fearlessness (*Nirbhayatā*) is Ḍa's
> *dissolved/spiritual* counter-pole — you reach it by dissolving the Shyness, it is not the printed
> reading. The earlier "*the* = Fearless creation" note used the spiritual pole and is retired here.

## Segmentation (how a word → varṇas) — **AUTO by default**
You must read the **sounds**, not the spelling. So the lens auto-routes:
- **Has IAST diacritics** (ā, ī, ṛ, ṅ, ṭ, ḍ, ś, ṣ …) → **literal** Sanskrit reading (the letters *are* the sounds).
- **A real dictionary word** (English/other) → **g2p**: word → pronunciation → varṇas
  (e.g. *phone* → F OW N → Pha·o·Na; *knee* → N IY → Na·ī; *the* → DH AH → Ḍa·a).
- **Otherwise** → literal fallback.

English↔Sanskrit sound notes: English **f** = **Pha** (p stays Pa); English voiced **th** (the/this) = **Ḍa**.
Overrides: `--g2p` force pronunciation · `--roman` force literal · `--varnas "va,a,ra"` pin exact varṇas.

### Retroflex vs dental — writing the two T/D/N families unambiguously
The **retroflex Ṭa-varga** (ṭ ṭh ḍ ḍh ṇ) and the **dental ta-varga** (t th d dh n) are different sounds with
different vṛttis (e.g. ḍa = *Lajjā/Shyness*, but da = *Krodha/Peevishness*). To write the **retroflex** in
manual/`--varnas` input, use **either**:
- **diacritics:** `ṭ ṭh ḍ ḍh ṇ ṣ` (e.g. `ḍa`), or
- **ITRANS capitals:** `T Th D Dh N` and `Sh` (=ṣa) — e.g. `Da` = **Ḍa** (Shyness); lowercase `da` = dental
  **Da** (Peevishness); `sh` stays palatal **Śa**.

English words go through g2p and are disambiguated automatically (voiced *th*→Ḍa, plain *d*→Da). Every
reading prints the **Devanāgarī + varga** (e.g. `ड Ḍa [RETROFLEX · Ṭa-varga]`) so you can confirm the sound.

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
