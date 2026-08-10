# Ground-Truth Protocol (Phase 6)

*`minimal_evidence_policy/ground_truth.py`. Independent gold labels over the minimal E0–ER vocabulary.
Ground truth is **not** derived from the minimal policy.*

## Independence

`ground_truth.py` does not import `policy.py`, `invariants.py`, or `modifiers.py`. Metadata is a shared
surface derivation; the two obligation rubrics (A: risk + claim-type; B: decision-impact + source) are
authored separately. Scoring the policy against this gold is therefore not circular (verified by test).

## Labels per item

factual vs non-factual; risk; claim family; source role; actionability; temporal sensitivity;
`gold_obligation` (E0–ER); `acceptable_obligations`; `unsafe_obligations` (levels below the annotators'
floor); `human_review_required`.

## Adjudication (conservative)

Gold = the **higher-burden** of annotator A and B. Acceptable = {A, B, gold}. Unsafe = any level strictly
below the lower annotation. High-risk disagreement resolves upward, never optimistically.

## Dataset (4 partitions, none overlapping prior sets)

| Partition | Count | Gold spread (E1/E2/E3/E4/ER) |
|---|---|---|
| DEVELOPMENT | 100 | 33 / 23 / 33 / 11 / 0 |
| HELD_OUT_NATURAL | 250 | 85 / 56 / 88 / 21 / 0 |
| ADVERSARIAL_INVARIANTS | 75 | 6 / 0 / 55 / 0 / 14 |
| HUMAN_REVIEW_SET | 50 | 13 / 13 / 12 / 12 / 0 |

676 new natural artifacts available (SUFFICIENT); excludes all prior source paths (bounded_shadow_pilot
857-set + evidence_obligation dev/held-out). Deterministic; the human-review set is balanced across
obligation classes.

## Annotator agreement — a simplification win

| Track | Vocabulary | Exact agreement (natural) |
|---|---|---|
| Prior evidence_obligation | 14 obligation types | 0.316 |
| **This track** | **6 levels (E0–ER)** | **0.640** |

The coarser vocabulary **doubles** exact annotator agreement. This is direct evidence that the prior
14-type resolution exceeded what the labels support, and that the minimal vocabulary produces
**more stable ground truth** — a benefit the simplification thesis predicted. (Real human agreement is
still measured separately in Phase 12; this is the independent-rubric proxy.)

## High-risk disagreement policy

Never resolved toward the lower burden; a large-gap high-risk disagreement floors gold at the higher
annotation. `unsafe_obligations` records the levels that would be unsafe for the item, used by the
downstream safety metric.
