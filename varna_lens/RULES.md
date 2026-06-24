# Varṇa Lens — The Rule (single, worldly-reference order-polarity)

> Interpretive lens — not a universal claim, not part of C×R×S. One frozen lexicon
> (`lexicon_authoritative.json`), one rule, applied identically every time.

## The reference: the WORLDLY (bīja) propensity
Every varṇa is read by its **one worldly (bīja-akshara) propensity** — the thing the sound *activates* in
the world. We never print the spiritual word directly: **the spiritual pole is what you get by dissolving
the worldly one**, and the rule below tells you, position by position, whether the word's sound-order is
**affirming** that worldly propensity or **eliminating** it.

- For a **consonant** the worldly propensity is its **binding (`negative`-field) vṛtti** — Ka = *Āśā* (Hope),
  La = *Krūratā* (Cruelty), Ra = *Annihilation*, Ḍa = *Lajjā* (Shyness), …
- For a **vowel** the worldly propensity is its **active (`positive`-field) essence** — a = *Birth of
  cognition*, ai = *Welfare / materialization*, … (the lexicon stores the vowel's worldly pole in the
  opposite field from the consonant's — this asymmetry is real, not a bug; the rule reads each from the
  correct field.)

## The one rule (worldly-reference order-polarity)
The **displayed meaning is always the worldly propensity**. Sound order only sets the **sign**:

- **+ AFFIRMED** — the bīja activates the propensity. A **consonant** has a **vowel after it** *and is not
  the word's first sound*; a **vowel** has a **consonant before it** (anchored).
- **− DISSOLVING** — the structure is *eliminating* that worldly propensity (→ its spiritual pole, which
  you derive). The varṇa **LEADS the word** (the bare first sound, **vowel or consonant**) or a **consonant**
  sits as a **coda** (vowel before, none after).

(The **first varṇa of the word is always −**, whether vowel or consonant — symmetric. For a leading vowel
this is automatic (nothing precedes); for a leading consonant it is an explicit override. e.g.
*the* = Ḍa⁻ **Shyness** ⟹ [a]; *kāla* = Ka⁻ Hope → ā⁺ → La⁻ Cruelty.)

(A consonant looks **forward** for its vowel; a vowel looks **backward** for its consonant — mirror images,
"and vice versa".)

**Final-vowel rule:** a vowel at the **end** of the word is **removed from the stitched chain** and reported
separately as the **whole-word essence** (it summarizes the word). Removing it turns the **preceding
consonant into a coda → −/dissolving.** (e.g. *lobha* → drop final *a* → *bh* becomes a coda → −*Deluded
obsession*; the dropped *a* = the word's summary essence.)

So: **consonant ⟶ worldly `negative`-field vṛtti**, **vowel ⟶ worldly `positive`-field essence**, every
varṇa in order with its **+/−** sign, **⟹ [whole-word essence]**. The per-letter *dissolved/spiritual*
counter-pole is still shown as `(counter: …)` in the full sequence view, for reading the dissolution.

### Worked examples (worldly reference)
| word | reading | whole-word essence (final vowel) |
|---|---|---|
| **lobha** | La⁻ Cruelty (leads) → o⁺ Closure → **Bha⁻ Deluded obsession** | a⁺ Birth |
| **love** | La⁻ Cruelty (leads) → a⁺ Birth → **Va⁻ Adharma (deviation from stance)** | (ends on Va) |
| **kāla** | Ka⁻ **Hope** (leads) → ā⁺ Expansion → **La⁻ Cruelty** | a⁺ Birth |
| **war** | Va⁻ **Adharma** (leads) → a⁺ Birth → **Ra⁻ Annihilation** | — (ends in consonant) |
| **the** | Ḍa⁻ **Shyness** (leads) | a⁺ Birth |
| **aim** | ai⁻ Welfare/materialization (leads) → **Ma⁻ Indulgence** (m eliminates it) | — |
| **ak** | a⁻ Birth (leads) → Ka⁻ **Hope** (coda) | — |

(Note the worldly *word* still reads the same — *kāla* is still "Hope … Cruelty" — only the leading sound's
**sign** is now − instead of +, marking the seed as un-anchored/dissolving rather than projected.)

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
