# ActionGate — Technology Readiness Level (TRL) Assessment

Standard NASA/DoD 9-level scale. The estimate is **evidence-based and conservative**; it states
what supports each level and what blocks the next. **[evidence]** = grounded in repo/tests;
**[interpretation]** = judgement.

## Estimate

**Overall: TRL 4** (technology validated in the laboratory), with the **isolated deployment
subsystem reaching TRL 5** (validated in a relevant environment). **Not yet TRL 6** — the
relevant-environment demonstration is incomplete and unverified in this audit.

## Level-by-level evidence

### TRL 1–3 (principles → proof of concept) — **met [evidence]**
- Written specifications: `ACTION_GATE_SPECIFICATION.md`, `ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`.
- Working reference engine (`action_gate_ref`) implementing a pure, deterministic decision function.

### TRL 4 (validated in the lab) — **met [evidence]**
- **24/24 conformance vectors** passing (`conformance.py`), including canonicalization, hashing,
  domain-separation, replay (`E_NONCE_REPLAY`), and TOCTOU (`E_STALE_STATE`) with pinned digests.
- **183** reference tests, **49** gateway, **51** MCP passing.
- Remediation R1/R1.5/R2 with a **measured** 153-scenario retry-governance study and security
  invariants (no DENY bypass, fresh hash per modification, no token reuse).
- **Real-world workflow validation:** 5 workflows, **12/12 injected attacks detected** with real
  error codes at real detection points (`real_world_validation/`).

### TRL 5 (validated in a relevant environment) — **partially met by the isolated subsystem [evidence/interpretation]**
Supporting evidence (`action_gateway_isolated/`, ~2,850 LOC):
- **Ed25519 asymmetric signing** with verify≠sign authority and trust-root pinning (`crypto.py`).
- **Durable, transactional replay/one-commit store** (SQLite `claim_nonce`/`claim_commit` +
  global watermarks, `replaystore.py`) — survives restart, DB-enforced uniqueness.
- **Durable signed audit ledger** with a **separate checkpoint-key custody** and UPDATE/DELETE
  triggers (`audit_ledger.py`).
- **Trust-domain-separated services** (agent → gateway over Unix socket; gateway → broker over
  **mTLS**), no authorization artifact returned to the agent (`gateway_service`/`broker_service`).
- **Bounded, DoS-resistant transport** (frame cap, read timeout, concurrency cap, `E_OVERLOADED`;
  `rpc.py`).
- A **30-attack compromised-agent red-team** run with real net-namespace/user isolation
  (`redteam.py`).

Why this is **TRL 5 and not higher [interpretation]:** it is a *relevant-environment* configuration
(real crypto, real IPC/mTLS, real durable stores, adversarial testing) but a **subsystem**, not a
complete operational system.

### Blockers to TRL 6+ [evidence/interpretation]
- **Unverified in this audit:** the isolated tier's dependency (`ecdsa`) is **absent in this
  environment** and its tests **skip**; it is read from source, not observed passing here.
- **Single-node only:** durable state is one SQLite file; **no HA, replication, or horizontal
  scale**; no throughput/latency evidence.
- **Operationally blind:** no logging, tracing, metrics export, dashboards, or alerting — a system
  demonstration in a relevant environment (TRL 6) needs operability.
- **Not production-qualified crypto:** pure-Python `ecdsa`, **no HSM/KMS**; no key/cert lifecycle.
- **No operational deployment:** nothing has run in a production-representative operational
  environment (TRL 7 territory).
- The **default runtime** (`action_gateway`) is still reference-grade (HMAC, in-memory + JSON
  snapshot), so the "product" as a whole sits at the reference tier unless the isolated tier is
  promoted to default and verified.

## Summary table
| level | status | key evidence / blocker |
|---|---|---|
| TRL 1–3 | ✅ met | specs + working reference engine |
| TRL 4 | ✅ met | 24 conformance vectors, 183+ tests, R2 study, 12/12 real-world attacks |
| TRL 5 | ◑ partial (isolated subsystem) | Ed25519 + durable stores + mTLS services + 30-attack red-team — but unverified here, single-node |
| TRL 6 | ✗ not met | no verified relevant-environment *system* demo; no HA/observability/scale |
| TRL 7–9 | ✗ not met | no operational deployment, no production crypto qualification |

## One-line assessment
**[interpretation]** ActionGate is a **lab-validated (TRL 4) technology with a production-leaning,
relevant-environment subsystem (TRL 5)**; reaching TRL 6 requires verifying and promoting the
isolated tier, adding observability, and demonstrating the full system (not just a subsystem) in a
representative environment.
