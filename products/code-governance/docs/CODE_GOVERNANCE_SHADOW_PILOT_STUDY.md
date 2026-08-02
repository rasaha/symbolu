# Shadow Pilot Study

> A bounded, evidence-based validation of the Code Governance shadow pilot. It
> answers whether Ugence catches governance conditions beyond ordinary CI, how
> often it produces unnecessary non-CLEAR outcomes, what causes disagreements,
> whether interventions route correctly, whether exact-commit binding is useful,
> whether the audit trail is complete, and whether there is enough demonstrated
> value to justify enforcement design. Execution stays DISABLED.

## Manifest, freeze, amendments

`PilotStudyManifest` binds the bounded study design (scope, dates, sample bounds,
policy/adapter/routing versions, reviewer protocol, permitted evidence classes,
success/pause/stop conditions) and fails closed on an unbounded or underspecified
study. A pre-pilot freeze binds all version inputs before collection; after
collection begins, changing a frozen input requires a new pilot revision or a
recorded `PilotAmendmentRecord` — never a silent policy change, and never a rewrite
of prior results.

## Live-run gate

A live pilot runs only when `UGENCE_CODE_GOVERNANCE_LIVE_PILOT=1` plus an explicit
manifest, tenant, repository/branch allowlists, durable-store path, read-only
credential reference, reviewer protocol, and maximum evaluation count are supplied.
Without them the tooling is built + validated offline and the live pilot is reported
as `LIVE_PILOT_NOT_RUN` — no live results are fabricated.

## Checkpoints + early-stop

`PRE_PILOT` / `EARLY_CHECKPOINT` / `MIDPOINT` / `PRE_CLOSEOUT` / `FINAL` checkpoints
summarize state and recommend continue/pause/stop. A critical safety failure
(credential leak, GitHub mutation, execution-enabled invariant failure, store
integrity failure, manifest mismatch, unapproved host/endpoint, cross-tenant
exposure) recommends STOP; collection must not continue merely to reach a target
sample after a critical failure. A checkpoint never enables enforcement.
