# Product-Readiness Assessment — Customer Shadow (M12)

*Each dimension scored independently (no overall percentage). This updates the pilot's assessment with
the controls this track added. Statuses: READY / LIMITED / PARTIAL / NOT READY / NOT EVALUATED. "READY"
here means **ready for a bounded shadow pilot**, never production.*

| Dimension | Prior (pilot) | Now | Basis |
|---|---|---|---|
| ActionGate integration | shadow mapping | **READY (shadow)** | real gate integrated read-only; 0 unsafe disagreement; deterministic |
| Architecture / contracts / audit / replay | READY | **READY** | inherited from the frozen pilot, unchanged |
| Safety evidence (shadow) | READY | **READY** | pilot 0 unsafe escape + real ActionGate stricter than shadow |
| Security (authn/authz boundary) | NOT EVALUATED | **LIMITED** | fail-closed HMAC boundary + scopes; not a real IdP |
| Tenant isolation | PARTIAL | **READY (shadow)** | own-tenant-only; cross-tenant denied; holds under concurrent load |
| Data classification / permitted-use | NOT EVALUATED | **READY (shadow)** | clearance lattice + classification |
| Redaction / minimization | PARTIAL | **READY (shadow)** | pattern redaction + field minimization on traces/exports |
| Secrets / encryption | NOT EVALUATED | **LIMITED** | interfaces + boundaries defined; **stubs, no real KMS** |
| Retention / deletion / export | NOT EVALUATED | **READY (shadow)** | tenant-scoped retention, erasure, minimized export |
| Secure artifact intake | NOT EVALUATED | **READY (shadow)** | size/format/clearance-bounded, redacted intake |
| Non-enforcing pilot API | NOT READY | **READY (shadow)** | fail-closed, tenant-scoped, `enforced=False` |
| Observability | PARTIAL | **LIMITED** | tenant metrics + alerts; no external backend |
| Incident response | NOT EVALUATED | **LIMITED** | severity taxonomy + detection→kill wiring + runbook; no on-call |
| Kill switches | (missing) | **READY** | pilot + tenant, fail-closed, checked first |
| Deployment packaging | NOT READY | **LIMITED** | pinned non-enforcing manifest + preflight; no image/IaC |
| Rollback / recovery | NOT EVALUATED | **READY (shadow)** | verified rollback-to-frozen-baseline procedure |
| Human-review workflow | LIMITED | **READY (shadow)** | tenant-scoped queue, no silent override |
| Latency (wall-clock) | PARTIAL | **LIMITED** | governance stages sub-ms; **no model call / no network** |
| Cost & storage | PARTIAL | **LIMITED** | bounded, minimized; real cost = the un-made model call |
| Load & concurrency | (missing) | **READY (shadow)** | ~2k rps, isolation held under concurrency |
| Security & isolation tests | (missing) | **READY** | operational fault sweep, all fail closed |
| Customer-pilot readiness | LIMITED | **READY (bounded, conditioned)** | eligibility gate PASS under scoped conditions |
| Production readiness | NOT READY | **NOT READY** | real IdP/KMS/deploy/model-latency NOT EVALUATED |

## Reading

- **Moved to READY (shadow):** tenant isolation, data classification/redaction/retention/erasure, secure
  intake, non-enforcing API, kill switches, rollback, human-review, load/concurrency, isolation tests —
  the core operational-safety surface of a bounded pilot.
- **LIMITED (real-but-shadow-grade):** security boundary, secrets/encryption, observability, incident
  response, deployment packaging, latency, cost — real controls sufficient for a bounded pilot but
  explicitly not production-grade (stubs / in-memory / no external systems).
- **NOT READY:** production readiness — real IdP, real KMS, distributed deployment, real model latency,
  SIEM/on-call remain NOT EVALUATED.

## Bottom line

The readiness track converted the pilot's operational gaps into **shadow-grade controls that pass a
fail-closed eligibility gate**. The runtime is ready for a **bounded, de-identified, non-enforcing
customer shadow pilot** — and explicitly **not** production-ready. The LIMITED dimensions are the exact
list of what a real IdP/KMS/observability/deploy stack must replace before scaling or handling
non-de-identified data.
