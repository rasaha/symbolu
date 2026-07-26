# Platform v1.0 — Security Boundaries

## Authority

- Only an **authenticated human** may create a binding decision; AI actors are
  advisory and can never be recorded as decision authority (F2/F3). Human approval
  cannot be fabricated by a provider (F15).
- Governance lifecycle records are owned by the DGM kernel (F1); providers and
  applications cannot mutate history.

## Fail-safe

- Provider infrastructure failure never yields support/authorization (F12);
  DENIED/INDETERMINATE never dispatch (F9/F10); unsupported assertions are never
  promoted without new evidence/authority (F11). Fallback is never used for
  governance shopping (F19).

## Isolation

- Providers interact only through neutral framework contracts (F16) and never
  import one another (F17). External execution is separate from authorization
  (F8) and providers never execute (F6).

## Data handling

- Observability records counts, coverage, outcomes, fingerprints, and error
  classes — **never secrets or unrestricted evidence**. Configuration carries
  secret *references* only; the platform implements no secret manager.
- Evidence provenance is preserved separately from evidentiary support; audit
  records never contain unrestricted source documents.

## Out of scope

Multi-tenancy redesign, live enterprise integrations, network transport security
of remote providers, and production deployment hardening are out of scope for the
frozen platform and are the responsibility of a deploying application.
