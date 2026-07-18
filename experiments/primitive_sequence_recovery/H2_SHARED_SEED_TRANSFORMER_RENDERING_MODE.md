# Design Memo — H2 Rendering Mode: Shared-Seed + Differentiating-Transformer Template

**Proposal only. Docs / rendering-mode spec — not an experiment, not a prereg, no runner, no code, no result.** This defines a *rendering mode* (how to display an onset-matched pair's frozen engine output), not a new claim. `like`/`love` remains **TOY_ONLY**. Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); Track B **BLOCKED**; no ontology, no Sanskrit privilege, no semantic-truth claim, no rescue of Track G.

## 1. Template definition
For an **onset-matched** pair (same leading varṇa), render *only* what the frozen engine emits, in a fixed 3-line form:

```
SHARED SEED  [varṇa {V0}, role=onset, sign={s0}]:  worldly={binding_gloss(V0)} ; counter={liberating_gloss(V0)}
{WORD_A} TRANSFORMER  [varṇa {Vk}, role={role}, sign={sk}]:  worldly={binding_gloss(Vk)}  ⤳ counter={liberating_gloss(Vk)}
{WORD_B} TRANSFORMER  [varṇa {Vj}, role={role}, sign={sj}]:  worldly={binding_gloss(Vj)}  ⤳ counter={liberating_gloss(Vj)}
```

Every `{…}` is pulled deterministically from `lexicon_authoritative.json` + the frozen positional rule. **Precondition:** `V0(WORD_A) == V0(WORD_B)` (else the pair is not onset-matched and is rejected before rendering). **Monosyllable clause:** when the DB model yields "all distortion / no balance," the template must render the seed + each differentiator explicitly and label the pair `NO_RESOLUTION_STAGE` (it does not invent a balance term).

## 2. Allowed fields (frozen only)
- varṇa key + IAST (`La`, `Ka`, `Va`)
- positional **role** (onset / coda / first-syllable / later) — from the rule, not chosen
- **sign** (`+`/`−`) — from the rule
- `binding_state` gloss, `liberating_state` gloss — verbatim from the lexicon
- the `⤳` transform marker; the literal labels `SHARED SEED` / `TRANSFORMER` / `NO_RESOLUTION_STAGE`

## 3. Forbidden fields (contamination)
- The target word's **dictionary meaning** or any sense label (preference, bonding, devotion, affinity…)
- Any **English semantic gradient** word not present in the lexicon
- Any **bridge phrase**: "= / means / represents / corresponds to / signifies / can be read as"
- Any **aptness/tone connective** ("resolves beautifully," "naturally becomes," "fits")
- Any adjective, ordering, or emphasis that a human adds to make the reading feel right
- Any **post-hoc pole selection** — the worldly/counter and sign are fixed by rule, never picked per word

If a rendering cannot be produced without adding a forbidden field, the item is void. In particular: **no Detachment⇒preference, no Dharma⇒bonding.**

## 4. Example — `like` vs `love` (frozen terms only)
```
SHARED SEED  [La, role=onset, sign=−]:  worldly=Krūratā (Cruelty) ; counter=Karuṇā/Sneha (Compassion/Gentleness)
like  TRANSFORMER  [Ka, role=coda, sign=−]:  worldly=Āśā (Hope)      ⤳ counter=Nirāśā (Detachment)
love  TRANSFORMER  [Va, role=coda, sign=−]:  worldly=Adharma (deviation) ⤳ counter=Dharma (sustaining order)
```
That is the **entire** legitimate output. Nothing that says Detachment⇒preference or Dharma⇒bonding — those were the post-hoc steps and are banned.

## 5. Leakage risks
1. **Post-hoc gloss-selection** (the main risk): re-reading `Nirāśā` as "liking" or `Dharma` as "love." Blocked by §3, but must be enforced by the leak scanner.
2. **Word recognizability**: a judge may reconstruct the word from the varṇa chain — anonymize; hide word identity and varṇa keys from the judge; present only the abstract gloss structure with shuffled A/B labels.
3. **Counter-pole degree of freedom**: worldly-vs-liberating and the sign must be **frozen by rule**; allowing per-word choice re-opens overfitting.
4. **Monosyllable collapse**: short English words give "all distortion," so the "differentiating transformer" may be a coda taken at its worldly pole only — the template must not fabricate a resolution.
5. **Onset-match illusion**: matching the *written* onset but not the *pronounced* one (needs G2P; recall the engine silently falls back to spelling if nltk absent).

## 6. Scoring proposal
- Judge sees the **anonymized** template rendering (word identity, varṇa keys, target sense hidden) and must match each rendering to a sense/gradient from a **frozen, independently-authored inventory** (forced choice).
- **Arms:** `A` real lexicon · `R` random-symbolic · `S` scrambled (permute (worldly,counter) pairs among consonants; vowel essences among vowels) · `F` sign-flipped roles · `X` context-only · `D` dictionary-only.
- **Pass gate (pre-registered):** for a signal, `A` must beat **S, R, F** (specificity) **and** **X, D** (incremental utility), each by a CI-lower-bound > 0 over N onset-matched pairs. `A_vs_S`, `A_vs_R`, and `A_vs_X` co-primary.
- **NO_SIGNAL** if scrambled/random render **as apt** as real (`A ≈ S` or `A ≈ R`).
- **NO_INCREMENTAL_UTILITY** if `X` or `D` matches/beats `A` (context or dictionary already solves the pair).

## 7. Kill criteria
- `A ≈ S` or `A ≈ R` → **NO_SIGNAL** (scramble/random equally apt).
- `X` or `D` dominates → **NO_INCREMENTAL_UTILITY**.
- Any rendering needs a **forbidden field** to read well → void (storytelling).
- Onset not truly matched (spelling vs G2P) → invalid item.
- Monosyllable pairs where the template yields no differentiating structure → drop.
- Judge recognizes words / leakage detected → discard.
- Any move to claim ontology, Sanskrit privilege, semantic truth, or to rescue Track G → stop.

## 8. Classification of `like` vs `love`
**TOY_ONLY** unless placed inside a full pre-registered audit with all §6 controls. Even then it is a *weak* item: monosyllabic (DB collapse), lexically trivial (X/D dominate), onset-shared. It illustrates the template; it is not evidence.

## 9. Recommendation
**Keep this as a docs-only rendering-mode spec now. Do NOT open a prereg on the template alone.**

- The template is a **legibility improvement**, not a source of signal — it makes "shared seed + differentiating transformer" explicit and comparable, which is genuinely useful for *displaying* results, but it changes nothing about whether the mapping carries meaning. The committed `varna_lens` synonym/archetype runs (same engine, with scramble/random) already returned **NO_SIGNAL**.
- A small prereg becomes justified **only if** you first assemble a proper item set: **onset-matched, multi-syllabic, frequency/familiarity-matched** synonym pairs (so DB produces a real arc and X/D don't trivially win), and commit to running them **blind against S/R/F/X/D** in the existing harness. The prereg gate is the **item set + controls**, not the rendering template.
- **Honest prior for such an audit: NO_SIGNAL** — the differentiator lives on the exact axis scramble/sign-flip neutralize, and Track G's random-flip already beat the real vector.

So: **docs-only rendering spec now; small-prereg-eligible only under the §6 controls and a matched item set, with a negative prior.** The reframe improved the *display*, not the *evidence*.

---

Guardrails preserved: Track G negative exact (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); Track B BLOCKED; no ontology, no Sanskrit privilege, no semantic-truth claim, no rescue of Track G.

Structure, not validated meaning.
