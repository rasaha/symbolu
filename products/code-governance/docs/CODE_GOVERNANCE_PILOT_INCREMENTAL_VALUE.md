# Pilot Incremental Value

> The central product question: does Ugence add information **beyond** existing
> GitHub and CI controls?

## Per-case classification

Each relevant case is labelled: `EXISTING_CI_ALREADY_CAUGHT`,
`GITHUB_RULE_ALREADY_CAUGHT`, `MANUAL_REVIEW_ALREADY_CAUGHT`, `UGENCE_UNIQUE_SIGNAL`,
`UGENCE_EARLIER_DETECTION`, `UGENCE_BETTER_ROUTING`, `UGENCE_BETTER_AUDITABILITY`,
`NO_INCREMENTAL_VALUE`, or `UNDETERMINED`. Multiple labels are allowed where
justified. A claim of unique detection or earlier detection **requires an evidence
reference** — the annotation model refuses a unique-value claim without one.

## Product-value decision

The report states plainly whether the pilot demonstrated any of: governance
conditions missed by CI, exact-SHA approval protection, useful cross-system
operational context, better authority routing, reduced unnecessary human review,
stronger audit reconstruction, or AI-agent change oversight. When none are
demonstrated, the verdict is `PRODUCT_VALUE_NOT_PROVEN`. Absence of evidence is
never reinterpreted as success.
