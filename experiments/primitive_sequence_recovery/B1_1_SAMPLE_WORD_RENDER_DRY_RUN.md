# B1.1 Sample-Word Render Dry Run (structural, pre-freeze)

## Status: `PASS_RENDER_DRY_RUN`

*(Re-run after the Ca de-Sanskritization fix, commit history: prior dry run `156c8da` was `REVIEW_REQUIRED`
on the Ca→"Viveka" leakage; that leakage is now removed.)*

## Scope and non-claims

Render-only structural preview of arm construction for a few sample words, **before** final freeze. This is
**NOT** model generation, **NOT** judging, **NOT** scoring, and is **NOT** evidence that B1.1 works or
outperforms B1/H2. Only the prompts/arm assignments that *would* be sent later are rendered — no answers are
generated. No model / embedding / generation / scoring / judging. Does **not** modify B1, change the verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology / Sanskrit privilege /
semantic-truth claim. **Structure, not validated meaning.**

> **Required caveat:** This render dry run is structural only. It provides **no evidence** that B1.1
> outperforms B1/H2. Performance evidence requires generation, blinded judging, and scoring **after** freeze
> and **separate** authorization. `R_deranged` remains the crux.

## Inputs & method

- **Word pool:** `COMMITTED_B1_POOL` (`b1_dry_run_harness.py` `PRIMARY_WORDS`); **8 sample words** selected
  deterministically (seed 70101): **echo, envy, integrity, justice, music, ocean, shadow, silence**. (The
  B1.1 word pool is not separately frozen; this reuses the committed B1 pool.)
- **Arms rendered:** A · R_same · R_deranged · R_domain · D · S · C · X (from committed configs + bridge pool).
- **Tasks rendered:** T1, T3, T4, T6 (committed B1 wording).
- **A's varṇa decomposition here is ILLUSTRATIVE spelling-based, NOT the frozen G2P** — the arm-builder runs
  real G2P→varṇa at generation time. Pool-based arms draw **real** committed bridge phrases; D/C are
  build-time slots; X is the bare task.

## Full prompt example (echo, arm A, T1) — post-fix

```
Soft orientation, not a definition: falsehood-discerning insight without egoic superiority — separates truth
from falsehood by detecting misperception, distortion, and false appearance ; realized knowing without
ownership — lets knowledge dissolve identity instead of forming spiritual ego. Use this only as a gentle
tonal/conceptual guide while following the task exactly.

Task:
Write a short reflective paragraph about echo.
```

## Structural review answers

- **Is A word-specific and coherent?** Yes structurally — A composes the target word's (illustrative) varṇa
  bridges; coherent English.
- **Is R_same fluent and strong?** Yes — real liberating-bridge phrases from the pool, not the word's own.
- **Is R_deranged fluent and strong, not nonsense?** Yes — another sample word's *real* A composition
  (fluent, strong, real-looking; wrong word). The crux control is fair and hard.
- **Is R_domain fluent and strong, not nonsense?** Yes — real phrases from a deterministically mismatched
  domain bucket (native ≠ assigned).
- **Does R_domain clearly use a mismatched domain?** Yes — each render records `native_bucket` ≠
  `mismatched_bucket`.
- **Does any arm leak labels A/R/D/S/C/X?** No — 0 arm-label leaks.
- **Does any arm reveal varṇa/Sanskrit terms?** **No — 0 proper Sanskrit nouns and 0 IAST diacritics in any
  bridge phrase after the Ca fix.** (Benign observation below.)
- **Are controls comparable in style/length?** Yes.
- **Is any control accidentally too weak?** No — 0 weak-control flags.
- **Does T4 preserve correctness sensitivity?** Yes — "Explain {w} plainly and accurately in 3-4 sentences."

## Leakage result (post-fix)

- **Proper Sanskrit nouns in bridge phrases:** **NONE** (the sole prior hit, `Ca`→"Viveka", is removed →
  now "falsehood-discerning insight").
- **IAST diacritics in bridge phrases:** **NONE.**
- **Arm-label leakage:** **NONE.**
- **Per-render leakage across the 8 samples × pool-based arms:** **0 hits.**

**Benign observation (not a blocker):** two owner-authored, dictionary-English guṇa adjectives remain in
`theory_owner_resolved` binding expressions — `rajasic` (Ra) and `sattvic` (Sa). These are common English
philosophical adjectives, are **not** varṇa-revealing proper terms, and were authored by the theory owner.
They are **not** changed here (that would exceed the Ca-only decision and alter owner wording); flagged for
an optional future owner decision.

## Weak-control / comparability

- Weak controls: **none**. R_same / R_deranged / R_domain are all real, fluent, comparable-length phrases.
- Comparability: pool-based arms are of similar richness; D/C/X are build-time slots of comparable structure.

## Status & next gate

- **Status: `PASS_RENDER_DRY_RUN`** — no leakage, no weak control, no malformed render.
- The **draft freeze manifest (`b1_1_freeze_manifest.draft.json`) is now STALE** (lexicon/bridge/report
  hashes changed with the Ca fix); it is **not** updated here.
- **Next gate: `B1_1_FREEZE_MANIFEST_REGENERATION`** (freeze validator `READY_FOR_FREEZE_REVIEW`, render
  `PASS_RENDER_DRY_RUN`).

## Final status block

```
dry_run_status:        PASS_RENDER_DRY_RUN
generation_run:        NO
B1.1 frozen:           NO
generation_authorized: NO
word_pool:             COMMITTED_B1_POOL (8 sampled, seed 70101)
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
draft_manifest:        STALE (regeneration is a separate gate)
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`) · Track F `CORRECTNESS_DEGRADED`.
`R_deranged` remains the crux. **Structure, not validated meaning.** Structural render only — no performance
evidence.
