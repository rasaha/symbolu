# Known Limitations & Non-Goals

This is the **authoritative** boundary for the AI Hiring product `0.6.0`. If a claim
elsewhere appears to exceed this list, this document governs. Every item is a
deliberate scope boundary of phases H0–H6, not a defect.

## Product maturity

- **Pre-1.0, not production-certified.** `version_info().production_certified` is
  always `False`. The package is suitable for evaluation, demonstration, and a
  controlled pilot only.
- **Public API may change before 1.0** (see [`VERSIONING.md`](VERSIONING.md)).

## No production external effects

- **No production integrations ship.** There are no HRIS, ATS, payroll, email,
  calendar, or identity-provisioning integrations — only replaceable ports and
  **deterministic provider implementations used only for validation**.
- **Execution is simulated.** The only supported execution mode is
  `DETERMINISTIC_SIMULATION`; production modes fail closed.
- **Consequential steps are not implemented.** `ISSUE_OFFER` and `SEND_REJECTION`
  (the contractual/communication steps) do **not** exist; only their
  non-consequential preparation steps (`PREPARE_OFFER`, `PREPARE_REJECTION`) do.

## No production-scale or compliance claims

- **No scale/performance claim.** Performance was characterized descriptively on a
  local single process only; there is no throughput, latency-at-scale, or capacity
  claim.
- **No fairness/compliance certification.** Fairness analysis is **read-only** and
  descriptive: it computes rate metrics by an analysis-only group label, applies
  small-sample discipline, and **never** enforces quotas, infers protected
  attributes, or labels the system "fair"/"unfair"/"compliant".
- **The shadow pilot is synthetic and bounded** (12 cases). It validates the
  lifecycle branches, not real-world outcomes.

## Governance boundary

- **The product package adds no governance.** It introduces no new decision,
  authorization, execution, or lifecycle semantics; it packages H0–H5. No frozen
  platform file is modified (freeze verification PASS).
- **Decisions are human-only** and **actions require authorization** — these are
  enforced, but they are properties of the frozen platform, not of this package.

## Persistence & identity

- **In-memory only.** All repositories are in-memory; nothing is durable across
  processes. The hash-chained audit exists only for the life of the process.
- **Static identity.** Identity and access grants are configured statically for
  demonstration; there is no enterprise IdP integration.

## Whole-repository baseline is not clean

The surrounding `symbolu` repository contains **pre-existing, unrelated** conditions
that are **not** part of this product and were not introduced or resolved by H0–H6:

- a `classify_change` freeze-tooling self-test failure, and
- `_SymboluFinder` collection errors in unrelated experimental modules
  (temporal / trading2 / voice / tools).

The product's green baseline is scoped to the platform-relevant packages
(`decision_governance`, `governance_providers`, `tap_provider`,
`actiongate_provider`, `ai_hiring`). **We do not claim a whole-repo green build.**

## Explicit non-goals of H6

H6 is packaging, documentation, and product wrap-up. It did **not** attempt: new
providers, model training or scoring, real integrations, fairness enforcement, a
service/server, durable persistence, or any production readiness certification.
