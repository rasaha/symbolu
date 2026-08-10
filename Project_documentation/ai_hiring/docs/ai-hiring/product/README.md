# AI Hiring — Product Overview

**Version:** `0.6.0` (pre-1.0 / controlled-pilot) · **Platform baseline:** Decision
Governance Platform `v1.0` (frozen) · **Production certified:** **No**

AI Hiring is a governed, evidence-grounded hiring **decision-support** application
built as a *consuming application* of the frozen Decision Governance Platform. It
demonstrates the full accountable lifecycle:

> Evidence → Recommendation → **TAP** assertion evaluation → Human review → Human
> decision → Action proposal → **ActionGate** authorization → External execution →
> Receipt → Reconciliation → Remediation/compensation → Auditable reconstruction

The core invariant — enforced in types, services, and persistence, not merely
documented — is:

> **The AI may recommend. A human decides. ActionGate authorizes. External systems
> execute. Ugence verifies, reconciles, and preserves the accountable record of
> what actually happened.**

## What this package is

- A **coherent, installable, demonstrable** packaging of the completed H0–H5
  implementation: a curated public API, typed fail-closed configuration, a safe
  deterministic demo, a CLI, and a human/machine-readable accountability report.
- Built **entirely** on the frozen platform; it adds **no** new governance
  architecture, hiring-decision semantics, authorization semantics, or production
  integrations.

## What this package is **not**

- It is **not** production software. No production HRIS/payroll/email/calendar/
  identity integrations ship here — only replaceable ports and **deterministic
  provider implementations used only for validation**.
- It makes **no** scale, quality, fairness, or compliance certification claim.
- The contractual consequential steps (`ISSUE_OFFER`, `SEND_REJECTION`) are **not**
  implemented; only their non-consequential preparation steps exist.

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for the authoritative boundary and
[`PRODUCT_CLAIMS_AUDIT.md`](PRODUCT_CLAIMS_AUDIT.md) for every product claim mapped to
its evidence.

## Documentation map

| Document | Purpose |
|---|---|
| [`INSTALL.md`](INSTALL.md) | Install and verify in a clean environment |
| [`QUICKSTART.md`](QUICKSTART.md) | Run the demo and read an accountability report |
| [`CONFIG_REFERENCE.md`](CONFIG_REFERENCE.md) | Every configuration key, fail-closed rules |
| [`API_REFERENCE.md`](API_REFERENCE.md) | The supported public API surface |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layering, dependency direction, lifecycle diagram |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Deployment posture and what a real deployment would require |
| [`OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md) | Operational procedures for the pilot package |
| [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md) | Security posture and boundaries |
| [`DEPENDENCY_REVIEW.md`](DEPENDENCY_REVIEW.md) | Dependency and supply-chain review |
| [`PACKAGING.md`](PACKAGING.md) | Packaging artifacts and the installable manifest |
| [`VERSIONING.md`](VERSIONING.md) | Pre-1.0 semantic-versioning policy |
| [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) | Authoritative limitations and non-goals |
| [`PRODUCT_CLAIMS_AUDIT.md`](PRODUCT_CLAIMS_AUDIT.md) | Each claim mapped to verifying evidence |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history H0–H6 |
