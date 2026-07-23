# Enterprise Deployment Model

*Phase 17. Deployment patterns for the control plane. **No single universal model** — the
right pattern depends on trust, latency, availability, and regulatory constraints. The
reference package is deployment-agnostic (stdlib, no I/O beyond an optional audit file), so
all six patterns are reachable from the same code.*

| Pattern | Trust model | Latency | Availability risk | Data exposure | Version mgmt | Tenant isolation | Audit ownership | Failure behavior | Suitable maturity |
|---|---|---|---|---|---|---|---|---|---|
| **Embedded library** | in-process, app is trusted | lowest (no network hop) | shares app's fate | app already holds the data | per-app deploy; version skew across apps | per-process | app owns log | app crash loses in-flight trace; fail-closed | early / single-app pilots |
| **Sidecar** | co-located, app↔sidecar trusted over localhost | low (localhost) | sidecar restart = local outage | data crosses localhost only | per-pod; canary per service | per-pod/tenant | sidecar → central store | sidecar down → app fails closed | per-service adoption |
| **Centralized service** | network-trusted, mutual auth | medium (RPC) | central SPOF; needs HA | data crosses network to service | single fleet, uniform version | logical, enforced by service | central, authoritative | service down → callers fail closed | org-wide standardization |
| **Gateway** | inline on the request path | medium; on critical path | inline SPOF; must be HA | sees all traffic (max exposure) | single choke point, easy rollout | per-route/tenant | gateway central | gateway down → requests blocked (fail closed) | uniform enforcement at scale |
| **Hybrid local/central** | local eligibility/policy, central audit+registry | low local, async central | local survives central outage | local minimizes; central gets records | local pinned, central authoritative | per-node local, central reconcile | central store, local buffer | central outage → local runs, buffers audit | regulated + low-latency needs |
| **Offline / regulated** | fully air-gapped | n/a (no external calls) | no external dependency | zero external egress | manual, controlled | physical | on-prem only | no provider path → MOCK/REPLAY only | high-regulation, evidence-only |

## Cross-cutting notes

- **Fail-closed is uniform.** In every pattern, control-plane unavailability blocks
  enforcement rather than allowing ungoverned execution — consistent with the invariants.
- **Audit ownership vs generation.** The component always *generates* append-only records;
  where they are *stored and owned* varies (app / sidecar-forwarded / central). The hash chain
  makes forwarded records tamper-evident regardless of transport.
- **Version management is the main operational risk** (Phase 16). Embedded/sidecar allow
  version skew across services; centralized/gateway trade a SPOF for uniform versions. Pins are
  per-trace immutable (invariant 10), so a mixed-version fleet stays *correct* per request but
  needs coordinated registry/policy rollout.
- **Latency vs exposure trade-off.** Gateway gives uniform enforcement at maximum data
  exposure and inline latency; embedded gives minimal latency and exposure but weak
  standardization. Hybrid is the pragmatic middle for regulated + latency-sensitive workloads.
- **Maturity progression.** A realistic path is embedded/sidecar pilots (MOCK/SHADOW) →
  centralized service (ADVISORY) → gateway (ENFORCEMENT) once shadow/advisory evidence
  justifies taking control. ENFORCEMENT is never the starting posture.
