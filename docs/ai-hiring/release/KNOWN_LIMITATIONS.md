# Known Limitations — Release-Level (Consolidated, Final)

Authoritative, consolidated limitations for the AI Hiring `0.6.0` controlled-pilot
release (frozen at `b9a0e3a`). This governs alongside
[`../product/KNOWN_LIMITATIONS.md`](../product/KNOWN_LIMITATIONS.md); where any other
statement appears to exceed this list, these limitations govern. Every item is a
deliberate scope boundary of phases H0–H6, not a defect.

## External effects — none in production

- **No production HRIS/ATS adapters.** Only replaceable ports + deterministic
  provider implementations used only for validation exist.
- **No production communication adapters.** No email, messaging, or calendar
  integration.
- **No employment-contract issuance.** `ISSUE_OFFER` is unimplemented; only the
  non-consequential `PREPARE_OFFER` exists.
- **No rejection communication.** `SEND_REJECTION` is unimplemented; only
  `PREPARE_REJECTION` exists.
- **No payroll integration.**
- **No identity provisioning.** Identity/access grants are configured statically for
  demonstration; no enterprise IdP integration.
- **Execution is simulated only.** `DETERMINISTIC_SIMULATION` is the only supported
  mode; production modes fail closed.

## Validation & analysis scope

- **Deterministic providers are validation-only.** They are deterministic provider
  implementations used only for validation — **not** production references or
  production-recommended implementations.
- **Bounded synthetic / de-identified pilot.** The shadow pilot and demo cohorts are
  small and synthetic; the controlled pilot uses synthetic or approved de-identified
  data only.
- **Fairness analysis is descriptive only.** Read-only rate metrics with small-sample
  discipline; it never enforces quotas, infers protected attributes, or labels the
  system "fair"/"unfair"/"compliant". No fairness or compliance certification.
- **Local performance measurements are not production benchmarks.** Timing was
  characterized on a local single process; there is no throughput/latency-at-scale or
  capacity claim.

## Product & maintenance

- **Pre-1.0, not production-certified.** `version_info().production_certified` is
  always `False`. The public API may change before 1.0.
- **In-memory persistence by default.** The shipped repositories are in-memory; a
  pilot requiring durable evidence must supply durable adapters for the platform's
  ports (a pilot-infrastructure task, not a product change).
- **Compatibility shims remain documented.** The `ai_hiring` namespace retains
  historical import paths and re-exports the canonical composition root; these
  backward-compatibility shims are intentional and documented.

## Repository baseline

- **Repository-wide unrelated baseline issues remain outside this release.** The
  surrounding `symbolu` repository has pre-existing, unrelated conditions — a
  `classify_change` freeze-tooling self-test failure and `_SymboluFinder` collection
  errors in experimental modules (temporal/trading2/voice/tools). These are **not**
  part of this product and were not introduced or resolved by H0–H6. **No whole-repo
  green build is claimed.** The release's green baseline is scoped to the
  platform-relevant packages (`decision_governance`, `governance_providers`,
  `tap_provider`, `actiongate_provider`, `ai_hiring`).

## Reproducibility

- **Wheel is bit-for-bit reproducible**; **sdist is content-reproducible** (identical
  file set + byte-identical file contents) but not bit-identical due to non-deterministic
  `tar.gz` archive framing in `setuptools 68.1.2`. Use the wheel for hash-pinned
  distribution. See [`RELEASE_MANIFEST.md`](RELEASE_MANIFEST.md).

## Deferred work (prerequisite to a future 1.0)

Production execution adapters (HRIS/ATS/payroll/email/calendar/identity), the
contractual `ISSUE_OFFER`/`SEND_REJECTION` steps, durable persistence, enterprise
identity integration, production-scale performance validation, and independent
fairness/compliance review — all explicitly out of scope for the controlled pilot.
