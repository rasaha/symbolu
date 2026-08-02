# Risk Register — Code Governance Implementation Readiness

> Documentation only. Verified at commit `3ec11e4e`. Categories: **architectural blocker** ·
> **implementation prerequisite** · **pilot prerequisite** · **production prerequisite** ·
> **future enhancement**. Priority: P0/P1/P2.

| # | Risk | Priority | Category | Basis | Mitigation |
|---|---|---|---|---|---|
| R1 | Incomplete governance-chain binding at dispatch | **P0** | implementation prerequisite | neutral `ExecutionDispatchRequest` carries no gov refs (§4.7) | Workflow Service fail-closed chain proof via DA `ExecutionIntent` (preferred) or reserved `parameters` keys → `CHAIN_INCOMPLETE` |
| R2 | No durable audit persistence for the decision kernel | **P0** | pilot/production prerequisite | DA repos/audit in-memory; chaining field reserved/unused | adopt/productionize StoryGraph/`agentic` hash-chained store; persist chain records |
| R3 | ACP is shadow-only, no GitHub domain, no durable clearance ref | **P0** | pilot prerequisite | `ACP_ARCHITECTURE.md:3`; no SCM adapter; ephemeral verdict | GitHub-domain ACP adapter + durable one-time clearance reference; shadow → recommendation → enforce |
| R4 | Exact merge-tree derivation (merge/squash) | P1 | implementation prerequisite | GitHub computes merge/squash trees | pre-compute expected merge-tree digest; bind in envelope; ACP re-verify at clearance |
| R5 | GitHub merge-queue semantics (artifact ≠ reviewed head) | P1 | implementation prerequisite | merge-group SHA differs | derived authorization bound to merge-group; re-validate + re-clear; defer to phase G |
| R6 | Rebase-merge instability (rewritten commits) | P1 | implementation prerequisite | per-commit SHAs not pre-knowable | bind tree + reconcile; else recommendation-only for rebase scope |
| R7 | Stale evidence not auto-invalidated | **P0** | implementation prerequisite | no head-SHA invalidation; no patch-hash watcher in DA | Workflow Service re-entry triggers on head/base/policy change; `ReasonCode.STALE_EVIDENCE` |
| R8 | Identity / role integration weak; SoD off by default | **P0** | pilot prerequisite | `segregation_of_duties=False` default; no enterprise OIDC; no GitHub role map | product policy sets SoD/required_approvals; map Code Owners/security to `AuthorityType`; OIDC (P2 §16.11) |
| R9 | No durable workflow engine (persistence/resume/event-sourcing/webhook) | **P0** | pilot prerequisite | `agent_runtime_v2` docs-only; `agent_runtime_migration` in-memory | Workflow Service owns durable state (phase A in-process; durable before 1C) |
| R10 | Token & credential handling | **P0** | implementation prerequisite | no webhook-sig/token-scoping code | least-privilege scoped installation tokens; no merge creds in agent envs; allowlists |
| R11 | Webhook replay | **P0** | implementation prerequisite | none exists | signature verification + delivery-id dedup (durable) |
| R12 | Policy drift / duplication across authorities | P1 | implementation prerequisite | multiple stores could diverge | single source of truth per rule (`POLICY_OWNERSHIP_MATRIX.md`); policy digest in `policy_refs` |
| R13 | One-time authorization consumption not native | **P0** | implementation prerequisite | ActionGate has no consume-once field | product consume-once envelope + durable consumption store |
| R14 | Execution reconciliation gaps | P1 | implementation prerequisite | DA reconciliation exists; merge-tree digest is product data | record + reconcile merge commit/tree digest against expected |
| R15 | Tenant isolation not wired through GPF resolution | P1 | implementation prerequisite | GPF resolution has no tenant scope | keep tenant in DA/product records; scope at product layer |
| R16 | Source-code residency for external-model adjudication | **P0** (MVP2) | pilot prerequisite | no residency gate | pre-external-model residency check; Model Selection routing |
| R17 | Unsupported commercial claims | P1 | production prerequisite | claim discipline (§15.1) | marketing bounded to: evidence-supported · policy-compliant · approved · artifact-bound · reconstructable · cleared |
| R18 | Claim manifest unsigned / no validator binding | **P0** | implementation prerequisite | no `ClaimManifest`; no validator id/version on evidence | product signed manifest schema + validator provenance binding |
| R19 | Build provenance / artifact-digest binding absent | P2 (MVP3) | production prerequisite | in-toto/SLSA/cosign not implemented | MVP3 deployment governance |

## Architectural blockers

**None.** No risk in this register requires redesign of authority or contract architecture. All are
**implementation / pilot / production prerequisites** or **future enhancements**. The rejected
three-GitHub-provider architecture is not reopened; no new `ProviderKind` is needed; no frozen
neutral contract must change for MVP.

## The critical P0 cluster (must close before enforced merge, MVP 1C)

R1 (chain binding) · R2 (durable audit) · R3 (ACP GitHub clearance) · R7 (stale invalidation) ·
R9 (durable workflow) · R10/R11 (tokens/webhook) · R13 (one-time consumption) · R18 (signed manifest
+ validator binding). Shadow (1A) and recommendation (1B) modes are reachable **before** most of these
close, which is exactly why the design sequences enforcement last.
