# Varṇa Lens — Word-Formation Rules (review & correct)

This is the **exact, complete** set of rules the lens uses to turn a word into an essence. Review each
stage; tell me what to change. (Interpretive lens — not a universal claim, not part of C×R×S.)

---

## STAGE 1 — Segment the word into varṇas (sounds)
How a word is broken into consonants (C) and vowels (V), **in pronounced order**.

- **Default (Sanskrit / romanized, IAST):** literal left-to-right. **No inherent "a" is added** — so
  `ka` = C(k)+V(a) but `ak` = V(a)+C(k). Aspirates/retroflex/sibilants are single units
  (kh, gh, ch, jh, ṭh, ḍh, th, dh, ph, bh, ś, ṣ, ṅ, ñ, ṇ, kṣ).
- **English (`--g2p`):** converted to phonemes via cmudict, then mapped to nearest varṇa (approximate —
  English `t`→dental `ta`, not retroflex `ṭa`; override with `--varnas`).
- **Manual (`--varnas`):** you give the exact varṇas, e.g. `ka,la` (authoritative).
- **Pronounceable units / syllables** (used by the `--db` rule): a syllable = onset + vowel + coda. A
  single consonant between vowels starts the **next** syllable; in a cluster the **last** consonant starts
  the next syllable and the rest close the current one. → `karma` = **kar** (k, r) + **ma**.

> ❓ Decision points: (a) inherent-"a" — keep literal (ka≠ak)? (b) where to split syllables (e.g. *water* =
> `wa·ter` or `wat·er`?).

---

## STAGE 2 — R1: each consonant is "created" or "destroyed" (by the vowel)
- Consonant **followed by a vowel** (CV, e.g. *ka*) → **created (+)**.
- Consonant with **no vowel of its own** (coda, e.g. the *r* in *war*) → **destroyed (−)**.

This is computed for every consonant. **How it's used depends on the model** (Stage 3).

---

## STAGE 3 — Pick each consonant's MEANING (which pole) — *4 models, pick one*
Every consonant has two poles in the lexicon: **negative vṛtti** (binding/distortion — the canonical
root) and **positive vṛtti** (liberating/balance). A model decides which pole each consonant uses.

| model | flag | rule for which pole | R1 used? |
|---|---|---|---|
| **Pairs** (original) | *(default)* | **always the NEGATIVE pole**; the +/− shown is only *position* (giver vs receiver), not pole | no (shown only) |
| **Reverse pairs** | `--reverse` | same as Pairs, but the 2nd consonant is the giver (causation backward) | no |
| **Distortion–Balance** | `--db` | **first syllable = NEGATIVE** pole (distortion); **all later consonants = POSITIVE** pole (balance) | no |
| **Vowel-pole** | `--vp` | **CV consonant = POSITIVE** pole; **coda consonant = NEGATIVE** pole (this is R1 deciding the pole) | yes |

Examples (same word, different model):
- *kāla* → Pairs: `Āśā(hope) → Krūratā(cruelty)` · Vowel-pole: `Nirāśā(detachment) → Karuṇā(compassion)`
- *war* → Vowel-pole: `Va⁺ Satya(truth) → Ra⁻ annihilation` = "righteous annihilation"

> ❓ Decision point: **which single model is "the" rule?** (They give very different readings.)

---

## STAGE 4 — Combine the consonants into the word essence (composition)
- **Pairs / Reverse:** read as **overlapping pairs** — `(C1 → C2) , (C2 → C3) , …`. First of each pair is
  the **giver (+)**, second is the **receiver (−)**. A middle consonant is receiver in its left pair and
  giver in its right pair. *kamala* = `Ka⁺→Ma⁻ , Ma⁺→La⁻`.
- **Distortion–Balance:** `DISTORTION seed = {first-syllable consonants, negative}` → `BALANCE = {rest,
  positive}`. *karma* = distortion(Hope·Annihilation) → balance(Disciplined restraint).
- **Vowel-pole:** a left-to-right chain of each consonant's chosen pole. *war* = `+Truth → −Annihilation`.

---

## STAGE 5 — Vowels  ⚠️ (currently NOT used in the essence)
Each vowel **is looked up** (its bridge aspect, positive/negative essence, layer movement) and **shown** in
the per-letter breakdown — but **no model currently folds the vowel's meaning into the composed essence.**
The essence is built from **consonants only**; vowels just (a) decide create/destroy via R1, and (b) display
for context.

> ❓ Big decision point: you've often read vowels as meaningful (o = closure, e = practical thought,
> a = raw potential). **Should vowels contribute to the essence?** If yes, tell me how — e.g. each vowel
> adds its positive (or negative?) essence between the consonants, or the **final** vowel "summarizes."

---

## STAGE 6 — Polarity sources, in one place (so nothing is hidden)
There are **three different +/− notions** in play — easy to conflate, so spelled out:
1. **R1 create/destroy** — does the consonant have a following vowel? (Stage 2)
2. **Pole** — which lexicon meaning, negative vs positive vṛtti. (Stage 3; chosen by the model)
3. **Position** — in Pairs, giver(+) vs receiver(−) by order. (Stage 4; labels only, not pole)

> ❓ Decision point: should these be unified? (e.g. "created ⇒ positive pole" is exactly what `--vp` does;
> the other models keep them separate.)

---

## What is FIXED vs a FREE CHOICE (for honesty)
- **Fixed (no choice):** the lexicon (each letter's two poles), segmentation, R1.
- **Free (a knob):** which **model** (Stage 3), syllable split, and whether/how **vowels** count (Stage 5).
  Every reading depends on these — changing a knob changes the essence, so to be testable they must be
  frozen **before** reading a word.

---

### Quick reference — run any word
```bash
python varna_lens.py "kāla"            # Pairs (default)
python varna_lens.py "kāla" --reverse  # Reverse pairs
python varna_lens.py "karma" --db      # Distortion–Balance
python varna_lens.py "war"   --vp      # Vowel-pole
python varna_lens.py "time"  --g2p     # English (approx)
python varna_lens.py --varnas "ka,la"  # manual segmentation
```
