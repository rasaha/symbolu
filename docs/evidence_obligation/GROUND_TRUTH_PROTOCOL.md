# Ground-Truth Protocol (Phase 7)

*`evidence_obligation/ground_truth.py`. Gold evidence-obligation labels for the dataset, produced by two
independent rubrics and adjudicated conservatively. Ground truth is **independent of the component under
test**.*

## Independence guarantee

`ground_truth.py` does **not** import `classifier.py`, `policy.py`, `obligations.py`, `taxonomy.py`,
`source_role.py`, or `authority.py`. Its obligation constants are bare strings and its keyword logic is
authored separately. Scoring the reference component against these labels is therefore not circular
(verified by test).

## Two annotation procedures

- **Annotator A — claim-type + source-role rubric.** Detects the claim family from content keywords and
  adjusts for the source-role hint (e.g. a code-behavior claim outside code weakens to contextual),
  emitting an obligation.
- **Annotator B — decision-impact + evidence-burden rubric.** Scores high-impact / measurable /
  absolute / non-assertive signals and emits an obligation from the *consequence* angle.

## Adjudication (conservative, never optimistic)

- **Gold = the higher-burden** of A and B; if either flags a high-external-burden obligation, gold is at
  least the strongest of the two.
- **High-risk disagreement is not resolved optimistically:** a large-gap disagreement (≥4 burden ranks)
  where one side is high-burden resolves to `HUMAN_REVIEW_REQUIRED`.
- **Unacceptable obligations** are recorded per item: for high-risk gold, any obligation weaker than the
  weaker annotation, and `NO_FACTUAL_EVIDENCE_GATE` is always unacceptable for a high-impact claim.

## Agreement (measured, reported honestly)

| Metric | Value (natural n = 400) |
|---|---|
| Exact-obligation agreement (14-class) | **0.345** |
| Directional agreement (low- vs high-burden) | **0.677** |
| Human-review rate (gold) | 0.188 |
| Risk distribution | low 277 / medium 23 / high 100 |

**Exact agreement is low (0.345).** This is expected — the two rubrics deliberately emphasize different
axes (claim-type vs decision-impact), so they often pick different-but-both-defensible obligations, which
is exactly why adjudication takes the higher burden. The **directional** agreement (do both see this as
low- or high-burden?) is 0.677. The low exact-agreement number is a **flagged risk for H0-14** (reviewers
disagree too much on fine obligation labels) and is examined directly in the Phase-20 review study; the
gold labels rely on *adjudication*, not on raw agreement, and high-risk items are conservatively floored.

## What each item records

`artifact_id`, `source_path`, `source_kind`, `source_role_hint`, `text` (redacted), `artifact_class`,
`claim_family` (gold), `risk_tier`, `gold_obligation`, `acceptable_obligations`,
`unacceptable_obligations`, `annotators_agree`, `human_review_required`, `synthetic`.

## High-risk disagreement policy

High-risk disagreement is never resolved toward the lower burden. It resolves to the higher burden or to
`HUMAN_REVIEW_REQUIRED`. This keeps the gold labels safe-by-construction: a claim the annotators dispute
in a way that could matter for safety is escalated, not quietly allowed.
