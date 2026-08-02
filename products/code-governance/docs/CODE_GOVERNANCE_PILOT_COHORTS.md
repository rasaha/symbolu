# Pilot Cohorts

> Cohort assignment is evidence-based and explainable. Machine-readable companion:
> `docs/pilot_cohorts.json`.

## Cohorts

`ROUTINE_LOW_RISK` · `SENSITIVE_CODE_PATH` · `AI_GENERATED_OR_AI_ASSISTED` ·
`STALE_HEAD_OR_REVISED_CHANGE` · `MISSING_OR_STALE_EVIDENCE` ·
`ACTIVE_CHANGE_RESTRICTION` · `INCIDENT_OR_OPERATIONAL_RISK` ·
`AUTHORITY_OR_SEPARATION_OF_DUTIES` · `CONFLICTING_SOURCE_SIGNALS` · `CONTROL_GROUP`.

An evaluation may belong to multiple cohorts, and cohort metrics are reported
separately. Code is **never** classified as AI-generated based on style or
speculation — only with an explicit provenance signal or a documented reviewer
classification. The AI-assisted cohort is analyzed separately (independent
validation, same-agent test generation, required human authority, sensitive-path
changes, stale-head frequency, reviewer burden, incremental findings) without
inferring that AI-generated code is inherently unsafe.
