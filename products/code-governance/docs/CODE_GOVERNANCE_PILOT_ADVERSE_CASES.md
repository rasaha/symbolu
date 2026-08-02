# Pilot Adverse Cases

> Every adverse case is individually reviewable and is never hidden inside an
> aggregate metric. Machine-readable companion: `docs/pilot_adverse_case_schema.json`.

## Kinds

Possible false CLEAR · possible unnecessary BLOCK · possible unnecessary ESCALATE ·
missed authority requirement · stale-head miss · source-conflict mishandling ·
policy amendment after start · reviewer safety concern · integrity anomaly ·
credential-or-boundary concern.

`collect_adverse_cases` assembles the list from evaluations, annotations, and
security findings. An unresolved serious possible-false-CLEAR case, or an unresolved
integrity/credential case, blocks the enforcement-readiness verdict. Adverse cases
are surfaced individually in the evidence pack and report, never summarized away.
