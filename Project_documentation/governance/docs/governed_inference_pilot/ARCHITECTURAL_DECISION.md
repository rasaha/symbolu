# Architectural Decision (Phase 29)

*Decided against the frozen evaluation (`EVALUATION_REPORT.md`) and readiness assessment
(`PRODUCT_READINESS_ASSESSMENT.md`). One primary decision, with the dimensions kept separate.*

## The eight options

| # | Option | Verdict |
|---|---|---|
| 1 | **PROCEED TO BOUNDED CUSTOMER SHADOW PILOT** | **Chosen** |
| 2 | Proceed with high-risk-only configuration | folded in (tier the config) |
| 3 | Proceed with minimum viable configuration | folded in (per-risk) |
| 4 | Fix contract/orchestration gaps first | **No** — contracts/orchestration are mature |
| 5 | Reduce component count | partial (drop CI/Scope from the safety core; keep for their own value) |
| 6 | Rework audit and replay first | **No** — audit/replay are READY (1.0/1.0) |
| 7 | Not enough evidence | **No** — 384 cases, 17 baselines, fault injection, MVC, cascade |
| 8 | Do not proceed to customer pilot | **No** — safety/audit/replay support a shadow pilot |

## Decision: Option 1 — proceed to a bounded customer shadow pilot

Proceed to a **bounded, shadow-only customer pilot** — the runtime observes real requests and produces
`WOULD_*` dispositions with full audit and replay, but performs **no enforcement and no external
action**. This is supported because, on the frozen corpus:

- unsafe assertion + action escape is **0.000** at **0.000** false-block, with no unsafe high-risk
  subgroup;
- audit completeness and replay determinism are **1.000**;
- every injected fault **fails closed**; no contract failure is silent; no external action occurs;
- a **commercially plausible minimum configuration** exists.

### Scoped by dimension (kept separate, per the readiness assessment)

- **Architectural viability:** READY. **Safety (shadow):** READY. **Audit / replay:** READY. **Contract
  maturity:** READY. These justify the shadow pilot.
- **Utility / latency / cost / operator usability / tenant isolation / observability:** PARTIAL or
  LIMITED — the shadow pilot's job is to convert these into live evidence.
- **Security / incident readiness / deployment / production:** NOT EVALUATED / NOT READY — **out of
  scope for a shadow pilot** and **required before any enforcing production deployment**.

### Configuration recommendation (folds in Options 2, 3, 5)

Run the shadow pilot **tiered by risk**, using the mandatory safety core the MVC study identified:

- **High/critical risk:** the full assertion+action core — ExecutionGate → ModelPolicy →
  EvidenceAssurance → AssertionGate → ActionGate. (ClaimIntegrity + ScopeIntegrity added no
  unsafe-escape reduction end-to-end here; keep them for claim traceability and the narrow
  scope-conjunction fix, but they are **not** load-bearing for the safety endpoint and may be omitted
  from the minimal safety configuration.)
- **Low risk:** the minimum viable control plane (ExecutionGate → ModelPolicy → AssertionGate + audit),
  accepting its higher escape only where the risk tier permits.

This is Option 1 *executed with* the reduction Option 5 recommends — smallest safe configuration per
risk, not the full stack everywhere.

## Explicit non-authorizations

- **No production, no enforcement, no external actions, no live provider calls by default, no customer
  data beyond de-identified/permitted, no silent human override.** The pilot remains shadow-only.
- **No claim of production readiness.** The decision authorizes a shadow pilot to gather the missing
  evidence, not a launch.

## What must precede production (from the readiness gaps)

Security threat model + authn/authz; enforced tenant isolation; live wall-clock latency and cost
measurement with real model calls; real human-review study; observability/alerting integration;
incident runbooks and rollback; deployment packaging. Each is a NOT-EVALUATED/NOT-READY dimension the
shadow pilot and subsequent work must close.

## One-line statement

> Proceed to a bounded, shadow-only customer pilot, tiered by risk around the EvidenceAssurance +
> AssertionGate + ActionGate safety core — the composition is correct, safe on structured cases, fails
> closed under fault, and is fully auditable and replayable. It is not production-ready; the pilot
> exists to convert the remaining PARTIAL/NOT-EVALUATED dimensions into live evidence before any
> enforcing deployment.
