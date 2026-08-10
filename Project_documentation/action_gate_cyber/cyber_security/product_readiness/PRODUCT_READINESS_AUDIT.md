# ActionGate — Product Readiness Audit

**Scope:** audit of the existing implementation against enterprise-product criteria. **No
capabilities invented.** Every line is tagged **[implemented]** (working code in the repo),
**[partial]** (present but reference-grade / single-node / not production-hardened), or
**[missing]** (not in the repo), with the file(s) that justify it.

**The single most important structural fact:** the codebase has **two maturity tiers**:
- the **reference core + main runtime** (`action_gate_ref`, `action_gateway`, `_mcp`, `_k8s`) —
  correctness-complete, conformance-tested, but reference-grade for crypto/storage/transport;
- a **hardened isolated deployment** (`action_gateway_isolated`) — production-leaning
  (Ed25519, durable SQLite stores, mTLS trust-domain services, bounded transport, 30-attack
  red-team) but **single-node** and, in this environment, **unverified** (its `ecdsa` dependency
  is absent and its tests skip). This tier is the productization path; it is not yet the default.

Audit environment caveat: the `action_gateway_isolated` suite could not be executed here
(dependency `ecdsa` not installed; cross-package tests skip/fail to collect on path). Its
implementations are read as **[implemented]** from source but **not verified-passing** in this
audit. The reference/runtime suites do pass: reference **183**, conformance **24/24**, gateway
**49**, MCP **51**.

---

## 1. Production security

| item | status | evidence |
|---|---|---|
| signing scheme | **[partial]** reference HMAC in the default path; **[implemented]** Ed25519 in the isolated tier | `action_gate_ref/signing.py` (HMAC, "stand-in", docstring says production asymmetric OUT OF SCOPE); `action_gateway_isolated/crypto.py` (Ed25519 via `ecdsa`, verify≠sign authority, trust-root pinning, `ISOLATION_NOT_PROVEN` on missing/old lib) |
| key management / custody | **[partial]** | isolated `layout.py`/`bootstrap.py` write private keys per domain + a public keyring; **[missing]** HSM/KMS integration, key rotation, revocation lists — no code |
| secret storage | **[partial]** | broker issues short-lived scoped capabilities, mints **no real secrets** (`action_gateway/broker.py`, `..._isolated/broker_core.py`); **[missing]** a real secret/credential source (vault/KMS) |
| certificate management | **[partial]** | isolated services use stdlib mTLS (`rpc.py`, `broker_service.py`), `k8s/kubeclient.py` uses a CA bundle + client cert; **[missing]** cert issuance/rotation/CA lifecycle (assumed pre-provisioned) |
| audit integrity | **[partial]** | reference: in-memory **tamper-evident** hash chain, "NOT tamper-proof, NOT a blockchain" (`audit.py`); isolated: **durable append-only SQLite ledger** with a **separate Ed25519 checkpoint signer** (custody split), UPDATE/DELETE blocked by triggers, external checkpoint detects truncation (`audit_ledger.py`); **[missing]** external WORM/replicated storage, retention policy |
| replay protection | **[partial→implemented]** | reference/runtime: process-local `_spent_nonces` set (lost on restart) — `gateway.py`; isolated: **durable, transactional SQLite claim-once** for nonces + one-commit-per-action + global sequence watermarks (`replaystore.py claim_nonce`/`claim_commit`) |
| policy versioning | **[partial]** | policy is signed + hashed + version string (`policy.py policy_version`); tokens/approvals bind `policy_hash`; commit rejects stale policy (`token.verify_token` → `E_POLICY_MISMATCH`); **[missing]** a policy registry, staged rollout, signed policy distribution/rotation service |
| recovery | **[partial]** | runtime `Gateway.snapshot()/restore()` to a JSON dict (`gateway.py`); isolated durable stores survive restart; **[missing]** backup/restore of the durable stores, DR runbooks, replication |

**Net:** the *security model* is sound and, in the isolated tier, backed by real asymmetric
crypto, durable claim-once replay, and a custody-split signed audit ledger. Production gaps are
**HSM/KMS, key/cert lifecycle, external WORM audit, and DR** — none present as code.

## 2. Scalability

| item | status | evidence |
|---|---|---|
| concurrency (correctness) | **[implemented]** | commit serialized by an `RLock` ("at most one commit under parallel duplicate execution", `gateway.py`); isolated adds DB-transactional claim-once so duplicate/parallel commit is DB-enforced (`replaystore.py`) |
| throughput / performance | **[missing]** | no benchmarks, load tests, or perf numbers anywhere |
| locking model | **[partial]** | a single process-level `RLock` around commit (not a lock manager); optimistic state-hash (TOCTOU) check at commit — see the transaction analysis. Fine for a single node; a bottleneck under scale |
| distributed deployment | **[partial]** | isolated multi-process trust-domain services over Unix socket + mTLS (`gateway_service`/`broker_service`); **[missing]** multi-node clustering, leader election, shared state across hosts (SQLite is one file) |
| high availability | **[missing]** | no replication, failover, or HA topology |
| horizontal scaling | **[missing]** | shared state is a single SQLite DB file (isolated) or in-memory (runtime); no partitioning/sharding |
| storage assumptions | **[partial]** | isolated = single-node SQLite; runtime = in-memory + JSON snapshot; **[missing]** a scalable durable backend (Postgres/replicated) |

**Net:** concurrency **correctness** is handled; **scale, throughput, HA, and horizontal
scaling are unaddressed** and gated by the single-node storage assumption.

## 3. Enterprise integration (summary; detail in ENTERPRISE_GAP_ANALYSIS.md)

- **[implemented]** Kubernetes — real stdlib REST client (`k8s/kubeclient.py`, mTLS/bearer, no
  shell) + adapter/server; MCP — transport adapter (`action_gateway_mcp`).
- **[implemented, sandbox-grade]** execution adapters: filesystem, shell, http, terraform,
  kubernetes, iam, monitoring (`action_gateway/adapters.py`) — demo adapters, not enterprise
  connectors.
- **[missing]** GitHub Actions, Jenkins, Azure DevOps, AWS, GCP, ServiceNow, Jira, SAP, **REST,
  gRPC**. The isolated services speak a **custom length-prefixed JSON RPC** (`rpc.py`), not
  REST/gRPC; there is no OpenAPI/proto.

## 4. Operations / observability

| item | status | evidence |
|---|---|---|
| metrics | **[partial]** | in-process counters in MCP only (`action_gateway_mcp/audit.py` `class Metrics` — "NEVER consulted for authorization"); no export |
| logging | **[missing]** | **no `logging.getLogger`/structured logging anywhere** in the codebase (grep-confirmed); audit is a domain concept, not operational logs |
| tracing | **[missing]** | no OpenTelemetry/spans |
| observability / dashboards | **[missing]** | no Prometheus/OTel/exporters, no dashboards |
| alerting | **[missing]** | none |

**Net:** operationally near-blind. The audit chain is a *forensic* record, not live telemetry.
**This is a P0 gap for any pilot.**

## 5. Compliance (architectural gaps only; detail in ENTERPRISE_GAP_ANALYSIS.md)

- **[partial]** Strong foundations for auditability: signed, hash-chained, custody-split durable
  ledger (isolated), deterministic decisions, non-repudiation via Ed25519.
- **[missing] architecturally:** RBAC/admin access control for operating the gate itself;
  encryption-at-rest configuration; data-retention/PII handling; external immutable (WORM)
  audit storage; SoD for gate operators; formal control mappings. SOC2/ISO27001/PCI/HIPAA each
  require several of these — none present as code or documented control mappings.

## 6. Developer experience

| item | status | evidence |
|---|---|---|
| SDKs | **[partial]** | Python in-process APIs + a client helper (`action_gateway_mcp/clientkit.py ClientSession`); **[missing]** published/multi-language SDKs, a network client library |
| API ergonomics | **[partial]** | clean Python function APIs + per-package CLIs; **[missing]** a stable network API surface (REST/gRPC), versioned API contract |
| documentation | **[implemented, internal]** | top-level specs (`ACTION_GATE_SPECIFICATION.md`, `ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`), per-package `README.md` + `IMPLEMENTATION_FINDINGS.md`; architecture study + validation reports; **[missing]** product/quickstart/onboarding/integration docs |
| onboarding / examples | **[partial]** | `demos/` in each package, red-team + real-world validation harnesses; **[missing]** a hosted quickstart, tutorials |
| testing | **[implemented]** | reference 183 + conformance 24, gateway 49, MCP 51, R2 study, real-world validation; **[partial]** cross-package tests need manual path setup (isolated suite fails to collect standalone) and the isolated tier is unverified without `ecdsa` |

**Net:** excellent *internal* rigor; **external DX (network SDK, REST/gRPC, onboarding docs,
reproducible cross-package tests)** is largely absent.

---

## Summary of maturity by category
| category | verdict |
|---|---|
| production security | model sound; isolated tier real; **HSM/KMS, key/cert lifecycle, WORM audit, DR missing** |
| scalability | correctness ok; **throughput/HA/horizontal/perf all missing** (single-node storage) |
| enterprise integration | K8s + MCP real; **REST/gRPC + all named enterprise systems missing** |
| operations | **near-blind** (no logging/tracing/metrics-export/alerting) |
| compliance | strong audit primitives; **RBAC/retention/encryption-at-rest/WORM/mappings missing** |
| developer experience | strong internal; **network SDK/API + onboarding docs missing** |

No production-code defect was discovered during this audit; the environment could not verify the
isolated tier (absent `ecdsa`). This is therefore a **documentation-only** deliverable.
