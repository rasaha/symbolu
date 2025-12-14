# SOULPI / Symbol-U Monorepo — Documentation Index

This is the single index of all documentation in the `/docs` directory.

## Classification Rule

**No loose documentation files are allowed at the `/docs` root.**

All documentation must be classified into one of the canonical subdirectories below. Only this `README.md` may exist at the root level.

## Directory Structure

| Directory | Purpose | Classification Rule |
|-----------|---------|---------------------|
| **`/docs/architecture/`** | Core system architecture, design documents, contracts, and boundary definitions | System design, routing contracts, architectural boundaries |
| **`/docs/phases/`** | Phase-specific documentation: merge safety reports, remediation reports, PR summaries, integration patches | Any document with `PHASE_*` prefix or phase-specific content |
| **`/docs/governance/`** | Governance policies, remediation plans, documentation rules | Policy documents, tier remediation plans |
| **`/docs/patent/`** | Patent verification, formula coverage, canonical implementations | IP-related documents, formal specifications, verification docs |
| **`/docs/migration/`** | Repository refactoring and migration plans | Directory normalization, extraction manifests, refactor plans |
| **`/docs/archive/`** | Historical references, catalogs, evolution documents | Legacy documents, master references, version evolution history |
| **`/docs/subsystems/`** | Subsystem-specific documentation | Acoustic, phonetic, mechanical subsystem docs |
| **`/docs/validation/`** | Validation strategies, test reports, stability audits | Invariance reports, testing docs, boundary validation |

## Adding New Documentation

1. Determine the appropriate category from the table above
2. Place the document in the corresponding subdirectory
3. Do NOT add files directly to `/docs/` root
