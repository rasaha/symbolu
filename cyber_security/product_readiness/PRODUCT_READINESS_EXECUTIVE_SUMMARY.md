# ActionGate — Product Readiness: Executive Summary

**Bottom line:** ActionGate is a **lab-validated technology (TRL 4)** with a **production-leaning,
relevant-environment subsystem (TRL 5)** already in the repo. The path to an enterprise pilot is
mostly **productizing and verifying what exists**, not inventing new capability — but there are
hard gaps in **operability, scale/HA, external APIs, and compliance controls** that must close first.
This summary is grounded in the code; it invents nothing and flags where evidence is missing.

## What is genuinely built (audited)
- A **correctness-complete reference engine** with a written spec, **24/24 conformance vectors**, and
  183 passing tests; deterministic decisions; replay/TOCTOU caught in tests.
- **Runtime integration** (gateway + MCP + Kubernetes) and **remediation** (R1/R1.5/R2) with a
  measured study; **real-world validation** detecting **12/12 injected attacks**.
- A **hardened isolated deployment tier** (`action_gateway_isolated`, ~2,850 LOC): **Ed25519**
  asymmetric signing with custody separation, **durable SQLite** replay/one-commit stores, a
  **signed, custody-split audit ledger**, **mTLS trust-domain services**, a **DoS-bounded transport**,
  and a **30-attack red-team**.

## The honest catch
- The **hardened tier is not the default and is unverified in this audit** — its `ecdsa` dependency
  is absent here and its tests skip. The default runtime is still reference-grade (HMAC, in-memory +
  JSON snapshot).
- It is **single-node** (one SQLite file): **no HA, horizontal scale, or performance evidence.**
- It is **operationally blind**: **no logging, tracing, metrics export, dashboards, or alerting**
  anywhere in the codebase.
- **No external API** (no REST/gRPC) and, besides **Kubernetes**, **none of the named enterprise
  integrations** (GitHub Actions, Jenkins, Azure DevOps, AWS, GCP, ServiceNow, Jira, SAP).
- Compliance-wise it is **audit-strong, operations-weak**: excellent non-repudiation/integrity
  primitives, but **no HSM/KMS, encryption-at-rest, WORM retention, operator RBAC, or control
  mappings.**

## Where it stands vs. what it needs
| dimension | today | needed for pilot (P0) | needed for launch (P1) |
|---|---|---|---|
| crypto/keys | HMAC default; Ed25519 in isolated tier (unverified) | promote+verify Ed25519, rotation runbook | HSM/KMS, encryption at rest |
| durability | in-memory (runtime) / SQLite (isolated) | backup/restore + retention | replicated HA backend, benchmarks |
| observability | in-process counters (MCP only) | logging + metrics export + health | tracing, dashboards, alerting, SLOs |
| external API | none (custom RPC) | one REST surface | SDKs + versioned contract + OpenAPI |
| integrations | Kubernetes + MCP | the pilot's one target/CI | AWS/GCP/ServiceNow/Jira/CI by demand |
| compliance | strong audit primitives | — | RBAC, WORM, mappings, PII handling, DR |

## The strategic read (interpretation)
The **hard, novel engineering is done** — the deterministic, evidence-bound, replay/TOCTOU-safe
commit core, and a real isolated deployment that removes the biggest reference-only caveats (HMAC,
process-local nonces, in-memory audit, single-threaded transport). What remains is **conventional
product hardening**: make the hardened tier the verified default, give it eyes (observability) and a
door (a REST API), and add the standard GA layers (KMS, HA/scale, RBAC, compliance mappings, SDKs).

**P0 (pilot)** is dominated by *promote + verify + operate + expose*, not by re-architecture.
**P1 (launch)** is the classic *scale / HA / compliance / SDK* build-out. **P2** items (multi-action
sagas, real-time control, a formal safety proof) would extend the model or scope and several are
explicitly gated on new evidence.

## Investment implication
The near-term spend is **productization of an existing, validated core** — the lowest-risk kind of
roadmap — with a clear, evidence-backed exit criterion for a pilot. The two things a buyer's security
team will ask for first (production crypto/key custody, and immutable auditable records) are the two
things the isolated tier already substantially provides; verifying and promoting that tier is the
single highest-leverage P0.

*(Detail: `PRODUCT_READINESS_AUDIT.md`, `ENTERPRISE_GAP_ANALYSIS.md`, `TRL_ASSESSMENT.md`,
`PRIORITIZED_PRODUCT_ROADMAP.md`.)*
