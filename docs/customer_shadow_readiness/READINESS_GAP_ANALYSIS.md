# Readiness Gap Analysis (M1)

*Derived from the completed pilot's `PRODUCT_READINESS_ASSESSMENT.md`. It scored the pilot READY on
architecture/contracts/audit/replay/shadow-safety and PARTIAL/NOT-EVALUATED/NOT-READY on the
operational and security dimensions. This document converts those into a prioritized work list for
customer-shadow readiness, with the ActionGate integration as the mandatory first gate.*

## Gap 0 (mandatory, first) — real ActionGate integration

| | |
|---|---|
| **Gap** | The pilot used a labelled ActionGate *shadow mapping*, not the real frozen ActionGate engine. |
| **Risk** | The shadow mapping is a conservative heuristic; the real engine may DENY less, ALLOW more, or apply constraints the shadow cannot express. If the real gate ALLOWs where the shadow blocked, the integrated pipeline becomes more permissive — a potential unsafe regression. |
| **Resolution** | Read-only real ActionGate adapter + differential corpus + disagreement/semantic-loss/determinism/latency measurement (M2–M3). |
| **Blocker rule** | Any case where the shadow mapping blocks but the real gate **unsafely allows** (permissive against ground truth) is a pilot blocker. |

## Prioritized operational gaps (after Gap 0)

| # | Dimension | Prior status | Readiness need |
|---|---|---|---|
| 1 | Security (authn/authz boundary) | NOT EVALUATED | non-enforcing auth boundary + threat surface for the pilot API |
| 2 | Tenant isolation | PARTIAL | enforced tenant scoping on requests/traces/artifacts; cross-tenant reference blocked |
| 3 | Data classification & permitted use | NOT EVALUATED | classify artifacts; block non-permitted use |
| 4 | Redaction & minimization | NOT EVALUATED | redact sensitive fields in traces/exports; minimize retained data |
| 5 | Secrets & encryption interfaces | NOT EVALUATED | interface stubs (no real keys); at-rest/in-transit boundary defined |
| 6 | Retention / deletion / export | NOT EVALUATED | tenant-scoped retention, deletion, and export controls |
| 7 | Secure artifact intake | NOT EVALUATED | validated, size/format-bounded, de-identified intake |
| 8 | Non-enforcing pilot API | NOT READY | shadow-only API surface (WOULD_* dispositions), never enforcing |
| 9 | Observability | PARTIAL | metrics/events over the audit trace; no external sink |
| 10 | Incident response | NOT EVALUATED | detection signals + runbook + severity taxonomy |
| 11 | Kill switches | (missing) | pilot-wide and tenant-level kill switches, fail-closed |
| 12 | Deployment packaging | NOT READY | reproducible, pinned, non-enforcing package manifest |
| 13 | Rollback & recovery | NOT EVALUATED | rollback to frozen baseline; recovery procedure |
| 14 | Human-review workflow | LIMITED | tenant-scoped review queue over the trace viewer |
| 15 | Latency (wall-clock) | PARTIAL | actual wall-clock measurement (governance stages only, no model call) |
| 16 | Cost & storage | PARTIAL | measured/bounded per-tenant cost and storage |
| 17 | Load & concurrency | (missing) | concurrency + throughput under bounded load |

## Reading

- **Gap 0 gates everything.** If the real ActionGate unsafely allows where the shadow blocked, the
  decision is FIX ACTIONGATE INTEGRATION FIRST regardless of the operational dimensions.
- The operational gaps are the difference between "shadow-safe on a synthetic corpus" (the pilot's
  result) and "safe to expose to a bounded external customer." Each is addressed as a non-enforcing,
  shadow-only control in this track; none enables production.
- **Nothing here enables enforcement or real actions.** Auth/tenant/data controls are *shadow-mode*
  guards over the read-only runtime; the pilot API never enforces and never executes an action.
