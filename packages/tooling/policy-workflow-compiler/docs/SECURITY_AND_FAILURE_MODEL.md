# Security and Failure Model

This tooling is built to fail closed, to hold no secrets, and to run offline. Its
security posture follows directly from those properties.

## Fail-closed

The pipeline halts on the first blocking finding. Any diagnostic at
`REVIEW_REQUIRED`, `ERROR`, or `FATAL` stops compilation, and there is no
best-effort or partial output (see `VALIDATION_MODEL.md`). The presence of a
compiled package is therefore positive evidence that every blocking rule passed;
the absence of one is the safe default.

## No secrets in packs

Policy packs are structured governance data and must not carry credentials or
secret material. The validation rule `EMBEDDED_SECRET` detects secret-like values
in a pack and raises a blocking diagnostic, keeping secrets out of compiled
packages, digests, and audit schemas.

## No network, no credentials

Core compilation performs no network calls and uses no credentials. The
capability registry resolves by **metadata only**; the optional `is_installed`
probe uses `find_spec` and **never imports** a provider (see
`CAPABILITY_REGISTRY.md`). The CLI `demo` is deterministic, offline, and
credential-free.

## Offline determinism

Because compilation is offline and deterministic, the same approved input plus
the same compiler version yields the same logical result regardless of
environment. Validation rejects `NON_DETERMINISTIC_VALUE` findings to protect
this property (see `DETERMINISM.md`). Distribution is reproducible: the wheel is
bit-for-bit reproducible and the sdist is content-reproducible.

## Named failure modes

| Failure mode | Trigger | Result |
| --- | --- | --- |
| Illegal lifecycle transition | e.g. `DRAFT->RELEASED`, `REVIEW_REQUIRED->COMPILED`, `INVALID->APPROVED` | `IllegalLifecycleTransition` raised. |
| Compile from non-approved pack | Pack not in `APPROVED` state | Compilation refused. |
| Missing provenance | Substantive object with no provenance | `PROPOSED_ONLY` / `REVIEW_REQUIRED`; excluded from synthesis. |
| Authority-boundary violation | Node crosses the ownership/disposition table | `FATAL` `AUTHORITY_BOUNDARY_VIOLATION`; compile halts. |
| Incomplete coverage | A required object has no assurance test | `INCOMPLETE_COVERAGE`; compile fails. |
| Embedded secret | Secret-like value in a pack | `EMBEDDED_SECRET` blocking diagnostic. |
| Non-deterministic value | Value that breaks reproducibility | `NON_DETERMINISTIC_VALUE` diagnostic. |
| Unknown capability | Reference to a capability not in the registry | `UNKNOWN_CAPABILITY` diagnostic. |
| Unsupported schema | Pack schema version not supported | `UNSUPPORTED_SCHEMA_VERSION` diagnostic. |
| Self-approval | Compiler process as approver (`COMPILER_PRINCIPAL`) | Approval rejected. |

Every failure mode above is deliberate and denies rather than degrades. See
`HUMAN_APPROVAL.md` for the self-approval rule and `AUTHORITY_BOUNDARIES.md` for
the boundary table.
