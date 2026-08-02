# Reviewer Feedback

> Human reviewer feedback is **audit data only**. It never retrains, modifies, or
> overrides policy, and it never changes the original clearance result.
> Machine-readable companion: `docs/pilot_feedback_schema.json`.

## Curated categories

Feedback uses an explainable, curated vocabulary rather than free-form sensitive
commentary.

**Agreement** — `AGREE`, `DISAGREE_STATUS`, `DISAGREE_INTERVENTION_REQUIRED`,
`DISAGREE_INTERVENTION_TYPE`, `DISAGREE_REQUIRED_AUTHORITY`,
`INSUFFICIENT_INFORMATION`, `SOURCE_DATA_INCORRECT`, `POLICY_CONFIGURATION_ISSUE`.

**Observed resolution** — `PROCEEDED_WITHOUT_CHANGE`, `WAITED_FOR_CONDITION`,
`REFRESHED_SIGNAL`, `REAUTHORIZED`, `CODE_CHANGED`, `HUMAN_EXCEPTION_APPROVED`,
`ABANDONED`, `UNKNOWN`.

An optional free-form note, if used, is classified via `comment_classification` and
excluded from normal metric calculations unless explicitly normalized.

## Binding + validation

Each feedback record links to the exact pilot evaluation (tenant + revision). It is
rejected if the tenant does not match, the evaluation is unknown, or (when the pilot
policy requires a reviewer role) the role is missing. Feedback is content-addressed
and persisted durably alongside the evaluation it comments on.

## Non-authority

Feedback is never a `DecisionRecord` and never an authority. It feeds descriptive
metrics (agreement rate, status/intervention disagreement, source-data-error rate,
possible-error categories) and is preserved for audit — a future policy change
based on it must be an explicit, human-driven, separately-authorized action, never
an automatic effect of recording feedback.
