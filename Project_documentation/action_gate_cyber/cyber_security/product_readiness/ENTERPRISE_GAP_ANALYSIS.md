# ActionGate — Enterprise Gap Analysis

Detail behind categories 3 (integration) and 5 (compliance) of the readiness audit. **[implemented]**
/ **[partial]** / **[missing]** are grounded in the repository; no capability is invented.

## 1. Integration surface — what exists

The engine authorizes **operations**; execution is delegated to **adapters**; callers reach it
through a **transport**. Enterprise integration therefore has three sub-surfaces.

### 1a. Transports (how a caller reaches ActionGate)
| transport | status | evidence |
|---|---|---|
| in-process Python API | **[implemented]** | `action_gateway.Gateway` (`submit/evaluate/execute`) |
| MCP (Model Context Protocol) | **[implemented]** | `action_gateway_mcp/` (server, protocol, registry, context, escalation) — a real agent-facing transport |
| Kubernetes admission/adapter server | **[implemented]** | `action_gateway_k8s/` (`server.py`, `kubeclient.py`) |
| custom length-prefixed JSON RPC (Unix socket + mTLS) | **[implemented]** | `action_gateway_isolated/rpc.py` (bounded frames, timeouts, concurrency cap) |
| **REST / HTTP API** | **[missing]** | no HTTP server, no OpenAPI |
| **gRPC** | **[missing]** | no proto/service definitions |

### 1b. Execution adapters (how ActionGate performs an authorized action)
| adapter | status | evidence |
|---|---|---|
| filesystem, shell, http, terraform, kubernetes, iam, monitoring | **[implemented, sandbox-grade]** | `action_gateway/adapters.py` — demo adapters operating in a sandbox root; not hardened connectors |
| Kubernetes (real API) | **[implemented]** | `action_gateway_k8s/kubeclient.py` — real HTTPS REST client with CA bundle + client-cert/bearer, structural requests, no shell/kubectl |

### 1c. Named enterprise systems (from the milestone)
| system | present? | note |
|---|---|---|
| Kubernetes | **[implemented]** | real REST client + adapter/server |
| GitHub Actions | **[missing]** | no action/workflow integration (the "GitHub coding agent" in real-world validation is a *narrative* mapped onto `DEPLOY`, not a GitHub Actions connector) |
| Jenkins | **[missing]** | — |
| Azure DevOps | **[missing]** | — |
| AWS | **[missing]** | IAM appears only as a policy *operation* (`IAM_GRANT_ADMIN`); there is no AWS SDK/API adapter |
| GCP | **[missing]** | — |
| ServiceNow | **[missing]** | no ITSM approval integration (approvals are internal signed artifacts) |
| Jira | **[missing]** | `linked_ticket` is an envelope field only; no Jira API |
| SAP | **[missing]** | — |
| REST | **[missing]** | see transports |
| gRPC | **[missing]** | see transports |

**Assessment [interpretation]:** integration breadth is **narrow but architecturally cheap to
extend** — per the architecture study, new systems are *adapters + transports around a domain-free
engine*, not engine changes. The engine already models the concepts these integrations need
(approvals, evidence, `linked_ticket`, `correlation_id`, delegation), so ServiceNow/Jira/CI
connectors are wiring, not redesign. But today only **Kubernetes** is a real enterprise-system
integration; everything else on the list is **missing**, and there is **no REST/gRPC surface** for
external callers to integrate against at all.

## 2. Compliance — architectural gaps only

The engine has unusually strong *auditability* primitives for a young system. The gaps below are
**architectural** (what a control framework requires that the code does not provide); this is not a
certification assessment.

### What already helps compliance [implemented/partial]
- Deterministic, reproducible authorization decisions (`gate.evaluate`) — supports change-control
  and non-repudiation evidence.
- Signed, hash-chained, **custody-split durable audit ledger** with UPDATE/DELETE blocked and
  external checkpoint (`action_gateway_isolated/audit_ledger.py`) — strong integrity/non-repudiation.
- Separation-of-duties in approvals (`approval.py` SoD + approver-count), and trust-domain
  isolation between agent/gateway/broker (`_isolated` services).
- Replay/one-commit durability (`replaystore.py`) — supports transaction integrity claims.

### Cross-framework architectural gaps [missing]
| control area | gap | applies to |
|---|---|---|
| **key management** | no HSM/KMS integration, key rotation, or revocation | SOC2, ISO27001, PCI, HIPAA |
| **encryption at rest** | no configured at-rest encryption for the durable stores/ledger | SOC2, PCI, HIPAA |
| **immutable retention** | audit is durable+signed but not external **WORM**; no retention schedule | SOC2, PCI (10y patterns), HIPAA (6y) |
| **operator RBAC / access control** | no role model or authN for *operating* the gate (who may change policy, read audit, run the broker) | all |
| **operator SoD** | policy signing, checkpoint custody, and broker operation are code-separated but there is no enforced operator-role model | SOC2, PCI |
| **PII / data classification** | envelope `arguments`/`objective` may carry sensitive data; no classification, masking, or DPA handling | HIPAA, PCI, GDPR-adjacent |
| **availability / DR** | no HA/backup/restore/DR (see readiness §2) | SOC2 (availability), ISO27001 |
| **monitoring / alerting** | no operational telemetry (see readiness §4) — SOC2 CC7 requires monitoring | SOC2, ISO27001 |
| **change management** | policy is signed/versioned but there is no approval-gated policy *deployment* pipeline or registry | SOC2, ISO27001 |
| **control mappings** | no documented mapping from ActionGate controls to SOC2 TSC / ISO Annex A / PCI DSS / HIPAA safeguards | all |

**Assessment [interpretation]:** ActionGate is **audit-strong, operations-weak** for compliance.
The hardest primitives to build (tamper-evident non-repudiable decision + execution records with
custody separation) exist; the missing pieces are conventional enterprise-ops controls (KMS, RBAC,
encryption-at-rest, retention/WORM, monitoring, DR) plus the paperwork (control mappings). None
require re-architecting the security model; all are additive.

## 3. Bottom line
- **Integration:** one real enterprise integration (Kubernetes) + agent transport (MCP); **no
  REST/gRPC and none of the other named systems.** Extensible by design, but currently narrow.
- **Compliance:** best-in-class audit/non-repudiation primitives (isolated tier); **standard
  enterprise-ops controls and control-framework mappings are absent.**
