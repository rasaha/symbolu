# B1.1 Sample-Word Render Dry Run (structural, pre-freeze)

## Status: `REVIEW_REQUIRED`

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

## Full prompt example (echo, arm A, T1)

```
Soft orientation, not a definition: falsehood-discerning Viveka without egoic superiority — separates truth
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
- **Is R_deranged fluent and strong, not nonsense?** Yes — it is another sample word's *real* A composition
  (fluent, strong, real-looking; wrong word). This is the crux control and it is a fair, hard control.
- **Is R_domain fluent and strong, not nonsense?** Yes — real phrases from a deterministically mismatched
  domain bucket (native≠assigned).
- **Does R_domain clearly use a mismatched domain?** Yes — each render records `native_bucket` ≠
  `mismatched_bucket`.
- **Does any arm leak labels A/R/D/S/C/X?** No — 0 arm-label leaks.
- **Does any arm reveal varṇa/Sanskrit terms?** **YES — see leakage finding below (the review trigger).**
- **Are controls comparable in style/length?** Yes — pool-based arms have similar richness/length; D/C/X are
  comparable build-time slots.
- **Is any control accidentally too weak?** No — 0 weak-control flags.
- **Does T4 preserve correctness sensitivity?** Yes — T4 = "Explain {w} plainly and accurately in 3-4
  sentences."

## Leakage finding (the review trigger)

**`Ca`'s `liberating_bridge` contains the Sanskrit term "Viveka"** — the only Sanskrit token in all 68 bridge
phrases (pool-level scan). Consequence in the render: **6 per-render hits**, all `sanskrit:Viveka`:

| word | arm | hit |
|---|---|---|
| echo | A | Viveka (composition includes Ca) |
| echo | S | Viveka |
| ocean | A | Viveka |
| ocean | S | Viveka |
| music | R_deranged | Viveka (deranged partner uses Ca) |
| silence | R_deranged | Viveka |

**Why it matters:** the conditioning is fed to the generation model. If the model echoes "Viveka" into a
Ca-conditioned output but not into non-Ca outputs, a judge could distinguish A/R by that token — a
**leakage confound**. Conditioning text should be plain English with **no** Sanskrit/varṇa terms.

**Recommended fix (next gate):** rewrite `Ca`'s `liberating_expression` to drop "Viveka" (e.g.
"falsehood-discerning insight without egoic superiority"), then **regenerate the bridge pool** and re-run the
leak scan. This is a lexicon edit → a separate, approved gate.

## Weak-control / comparability

- Weak controls: **none**. R_same / R_deranged / R_domain are all real, fluent, comparable-length phrases.
- Comparability: pool-based arms are of similar richness; D/C/X are build-time slots of comparable structure.

## Status & next gate

- **Status: `REVIEW_REQUIRED`** — driven solely by the `Ca`→"Viveka" Sanskrit leakage (no weak-control,
  no arm-label leak, no malformed render).
- **Next gate: `B1_1_ARM_CONSTRUCTION_REVIEW_FIXES`** — de-Sanskritize `Ca`'s bridge, regenerate the pool,
  re-run the bridge validator + leak scan, then re-render.

## Final status block

```
dry_run_status:        REVIEW_REQUIRED (Ca -> "Viveka" Sanskrit leakage)
generation_run:        NO
B1.1 frozen:           NO
generation_authorized: NO
word_pool:             COMMITTED_B1_POOL (8 sampled, seed 70101)
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`) · Track F `CORRECTNESS_DEGRADED`.
`R_deranged` remains the crux. **Structure, not validated meaning.** Structural render only — no performance
evidence.
