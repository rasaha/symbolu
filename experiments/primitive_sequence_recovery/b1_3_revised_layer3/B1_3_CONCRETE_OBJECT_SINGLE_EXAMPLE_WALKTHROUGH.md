# B1.3 Concrete-Object LLM Judged-Modulation — Single-Example Walkthrough (knife)

## 1. Scope

Explanatory walkthrough only. **No new run · no stimulus regeneration · no stimulus modification · no judge
run · no scoring · no EVIDENCE_FREEZE · no artifact change except this memo.** All values below are read
verbatim from the already-committed artifacts. **Structure, not validated meaning.**

## 2. Example target

Read from `b1_3_concrete_object_final_primary_wordlist.json` and the deranged map:

- **target word:** `knife`
- **item_id:** `co_020`
- **object family:** `tool`
- **dictionary anchor:** *"a cutting instrument with a blade and handle"*
- **neutral context:** *Consider the ordinary object "knife" in a plain, everyday sentence.*
- **WordNet synset:** `knife.n.01`

## 3. Real arm — `A_real` (step by step)

Traced through the actual bound pipeline:

1. **G2P (cmudict):** `knife` → phonemes `[('C','nna','N'), ('V','ai','AY1'), ('C','pha','F')]`.
2. **Consonant varṇas:** `nna` (N) and `pha` (F). (The vowel `ai` carries no consonant varṇa.)
3. **read_op pole rule (structural, referent-blind):** `nna` is the word's **first** consonant → **binding**;
   `pha` is **word-final** → **binding**. Both poles: `binding`.
4. **Bridge-pool gloss lookup** (`b1_2_varna_bridge_pool.json`):
   - `nna` binding → *"the sting at another's success"*
   - `pha` binding → *"collapse or flight before danger"*
5. **Gloss reduction to field tags** (shared-register rule: first plain non-stopword, non-Sanskrit token,
   preferring 4–6 chars, hyphen-split):
   - *"the sting at another's success"* → **`sting`**
   - *"collapse or flight before danger"* → **`flight`** (*collapse* is 8 chars → skipped for the shorter
     in-band token)
6. **Deterministic backfill to 4** (only 2 varṇas route, so 2 more tags are drawn from the seeded global tag
   pool, excluding leaks): → **`truth`, `open`**.
7. **Global rules applied uniformly:** anti-leak (no tag = `knife` or a WordNet synonym) · no-Sanskrit ·
   within-option dedupe · short-register normalization. None triggered a replacement here.
8. **Final `A_real` tags:** `['sting', 'flight', 'truth', 'open']`
   **Rendered option (verbatim from the draft stimuli):**
   > *"Within the fixed meaning, this object is modulated by sting, flight, truth, and open."*

No dictionary meaning was used to choose these tags; no per-item hand-polishing.

## 4. Deranged arms (near / mid / far)

Sources were assigned deterministically in the final screen (WordNet Wu-Palmer similarity, family separation,
least-used balancing, lexical tie-break) **before** any tags existed:

| stratum | source word | source family | basis | rendered other-option tags |
|---|---|---|---|---|
| **near** | `key` | tool (same family) | WuP 0.600 (highest-sim) | `hope, judgment, agency, higher` |
| **mid** | `tower` | structure (diff family) | WuP 0.526 (median) | `garrulous, driven, love, keeps` |
| **far** | `pillar` | structure (diff family) | WuP 0.095 (lowest-sim) | `turned, turns, sting, status` |

Each deranged option is the **source word's own `A_real` field** (e.g., `key`'s real varṇa tags), rendered in
the identical template. Interpretation:

- **near** (`key`, same tool family) — the **hard word-specificity** test: can the judge tell *knife's* field
  from a functionally-adjacent object's field?
- **mid** (`tower`) — the **primary object-specificity** control: a concrete object of a different function
  family, neither trivially far nor unfairly near.
- **far** (`pillar`) — the **easiest** control (very low similarity); beating far only would be category-level,
  not word-specific.

> **Honest pre-freeze note:** the mid option contains `garrulous` (9 chars), a longer **fallback** token that
> slipped past the 4–8 register band because `tower`'s gloss for that varṇa had no shorter in-band token, so the
> reducer fell back to the first candidate. The style-tell audit still passed (0.378) because such fallbacks are
> rare, but this is a legitimate **polish item to fix globally before freeze** (extend the reducer's fallback to
> enforce the band or truncate). It does **not** change any decision here and the frozen stimuli are **not**
> modified in this walkthrough.

## 5. Scrambled arm — `R_scrambled`

Same varṇa-derived tags as `knife`'s `A_real`, **order-disrupted** by a seeded permutation:
`['truth', 'open', 'flight', 'sting']` (the reverse-ish reorder of `sting, flight, truth, open`).
> *"Within the fixed meaning, this object is modulated by truth, open, flight, and sting."*

Because the multiset of tags is identical and only the order changes, this isolates whether **tag order /
structure** carries anything. It is the critical control given the prior automated finding scrambled≈real
(cosine 0.967).

## 6. Random arm — `R_random`

Four tags drawn by a fixed seed from the global tag pool, excluding `knife`'s own varṇa tags:
`['alert', 'agency', 'acting', 'limit']`.
> *"Within the fixed meaning, this object is modulated by alert, agency, acting, and limit."*

Tests whether **any coherent symbolic tag set** suffices (generic resonance), independent of `knife`'s varṇas.

## 7. Neutral arm — `X_neutral`

Content-free, no-varṇa filler tags (fixed, register-matched): `['aspect', 'factor', 'facet', 'nature']`.
> *"Within the fixed meaning, this object is modulated by aspect, factor, facet, and nature."*

Tests whether **modulation adds any value at all** over a bare, contentless rendering.

## 8. Semantic-only baseline

Dictionary/object-function tags derived from the **anchor only** (no varṇa input), leak-filtered, same format:
`['cutting', 'blade', 'handle', 'edge']`.
> *"Within the fixed meaning, this object is modulated by cutting, blade, handle, and edge."*

This is the **hardest** baseline for Symbol-U: these tags are the object's *ordinary function*. **If a judge
prefers this over (or equal to) `A_real`, the result is ordinary object semantics, not Symbol-U-specific** — the
scorer would return `LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS`. It is kept strictly separate from
`X_neutral` (content-free) and is never used as `A_real` or a control.

## 9. What the LLM judge will see (A_real vs R_deranged_mid)

Judge-facing block, exactly as presented (arm identities hidden; position from the frozen `position_seed`):

```
Object: knife
Dictionary meaning: a cutting instrument with a blade and handle
Context: Consider the ordinary object "knife" in a plain, everyday sentence.

Option A: Within the fixed meaning, this object is modulated by sting, flight, truth, and open.
Option B: Within the fixed meaning, this object is modulated by garrulous, driven, love, and keeps.

Question: Given the dictionary meaning of the object, which option gives a more fitting inner
tendency or field around this object without changing what it is?
Answer with exactly one letter: A or B. Optionally, on a second line, confidence 1-5.
```

**Hidden labels (never shown to the judge; stored in the private truth-map):** Option A = `A_real` (knife's own
varṇa field); Option B = `R_deranged_mid` (source `tower`'s field). Here `position_seed = 0` placed `A_real` on
the left (Option A); across the 53 objects the position is balanced so side gives no cue.

## 10. How scoring would interpret the answer

- If the judge answers **A** → the selected side's arm is `A_real` → **A_real gets one win** on
  `A_real_vs_R_deranged_mid` for `knife`.
- If the judge answers **B** → the selected arm is `R_deranged_mid` → **A_real gets one loss**.
- **Invalid handling:** a missing required field, `invalid_flag`, `parse_status ∈ {unparseable, refused,
  malformed, tie}`, or an unmappable selection → counted **invalid**, never repaired; if invalids exceed 10%
  the run is `LLM_OBJECT_MODULATION_INVALID_RUN`.
- This single judgment contributes **one Bernoulli trial** to the `A_real_vs_R_deranged_mid` win rate.
  Aggregated over all `knife`-mid judgments across the judge panel (and all 53 objects), the scorer computes a
  Wilson interval; the **primary threshold** is *lower CI bound > 0.50*. **One example decides nothing** — the
  thresholds evaluate the aggregate.

## 11. What this clarifies about the implementation

- The generator must emit **all seven arms** for each object in the **identical template** (it does — verified
  here for `knife`).
- **Hidden labels must stay hidden**: the judge sees only Option A/B + anchor + context; arm identity lives in
  the private truth-map read only at scoring.
- The **scoring script** depends solely on `arm_left`/`arm_right` + `selected_option` to award a win — this
  example shows exactly how a raw answer becomes a win/loss.
- The **style audit** exists to prevent surface giveaways (length/format); the `garrulous` fallback note in §4
  shows why an extra global register-polish pass is worth doing before freeze.
- The **semantic baseline** (`cutting, blade, handle, edge`) prevents ordinary dictionary-fit from being
  mistaken for a Symbol-U signal.
- **near/mid/far** stratification prevents an easy `far`-control win (`pillar`, WuP 0.095) from being
  overclaimed as word-specificity; the hard test is `near` (`key`, same tool family).

## 12. What would count as success across the full study

- **One example proves nothing.** Success is defined over all **53** primary concrete objects.
- **STRONG** — A_real beats **near, mid, far** deranged + scrambled + random + neutral + semantic baseline.
- **CATEGORY_LIMITED** — beats **mid and far** (+ other controls + baseline) but **not near** → a
  function-family effect, **no** word-specificity claim.
- **NULL** — A_real fails mid or far, or fails scrambled/random/neutral.
- **SEMANTIC_BASELINE_EXPLAINS** — the dictionary baseline matches/beats A_real (ordinary object semantics).
- Given the convergent prior nulls (real≈fake objects; scrambled≈real 0.967), the honest prior for a positive
  is **low**; the design is built so a null is believable and a positive is interpretable.

## 13. Final status block

```
document:                    B1.3 concrete-object SINGLE-EXAMPLE WALKTHROUGH (knife) — explanatory only
example object:              knife (item_id co_020, family tool)
arms shown:                  A_real / R_deranged_near(key) / mid(tower) / far(pillar) / R_scrambled / R_random /
                             X_neutral / semantic_only_baseline — all from existing draft stimuli
judge-facing example:        A_real vs R_deranged_mid (hidden labels disclosed only after the block)
new final stimuli generated: NO
stimuli modified:            NO
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
```

**Structure, not validated meaning.** This walkthrough only reads and explains existing artifacts for one
object; no stimuli were generated or modified, no judge was run, nothing was scored, prior nulls and closures
stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
