# Implementation Sequence — Code Governance MVP

> Documentation only. **No package is created by this audit.** Authoritative source:
> `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§13). Machine-readable form: `implementation_manifest.json`.

Enforcement is earned in rungs: **1A shadow → 1B recommendation → 1C enforced**. Later-MVP features
never silently become MVP-1 dependencies.

## Phase A — Product contracts & workflow skeleton
- **Prerequisites:** none.
- **Packages touched:** `products/code-governance/{workflow,api}` (new).
- **Contracts reused:** `DecisionRecord`, CER, `ActionGovernance*`, `Execution*`.
- **Contracts added:** PRODUCT_INTERNAL — `FrozenTaskEnvelope`, `PatchCandidate`,
  `ValidationEvidenceBundle`, `ExactChangeAuthorization` envelope, workflow state machine.
- **Authority impact:** none. **GitHub writes:** none. **Enforcement:** none.
- **Tests:** state-machine + reference-propagation unit tests; no GitHub I/O.
- **Acceptance:** all states/transitions covered; `CHAIN_INCOMPLETE` fail-closed simulated.
- **Rollback:** delete product package; no neutral change. **Evidence tier:** internal.

## Phase B — GitHub evidence ingestion (shadow)
- **Prerequisites:** A.
- **Packages:** `products/code-governance/{github_connector,evidence_mapping}`.
- **Contracts reused:** `AssertionGovernanceRequest.evidence_refs`.
- **Contracts added:** PRODUCT — PR/commit/check evidence records; **claim manifest schema**.
- **Authority impact:** none. **GitHub writes:** none (read-only). **Enforcement:** none.
- **Tests:** webhook-signature verification; installation-token auth; immutable evidence refs.
- **Acceptance:** shadow ingestion produces provenance-bound refs; no writes.
- **Rollback:** disable connector. **Evidence tier:** shadow.

## Phase C — TAP & decision integration (shadow → recommendation)
- **Prerequisites:** B.
- **Packages:** `products/code-governance/policy`.
- **Contracts reused:** TAP `evaluate`, `DecisionRecord`, `VersionedRef` policy_refs.
- **Contracts added:** PRODUCT — repository policy pack.
- **Authority impact:** uses DA + TAP as-is. **GitHub writes:** check-runs only (1B).
- **Tests:** claim manifest → TAP → `DecisionRecord` mapping in shadow; recommendation check-run.
- **Acceptance:** shadow decisions recorded; then 1B recommendation published; SoD/roles mapped.
- **Rollback:** revert to shadow. **Evidence tier:** recommendation.

## Phase D — Exact-action mapping (no execution)
- **Prerequisites:** C.
- **Packages:** `products/code-governance/action_mapping`.
- **Contracts reused:** CER, `ActionGovernanceRequest`, `ActionGovernanceResult`.
- **Contracts added:** PRODUCT_INTERNAL — merge identity tuple; `ExactChangeAuthorization` envelope.
- **Authority impact:** uses ActionGate as-is. **GitHub writes:** none. **Enforcement:** none.
- **Tests:** merge identity bound; CER + ActionGate authorize; envelope fingerprint; no dispatch.
- **Acceptance:** exact-artifact authorization produced without executing.
- **Rollback:** drop mapping. **Evidence tier:** recommendation.

## Phase E — ACP live clearance (shadow first)
- **Prerequisites:** D; ACP GitHub-domain adapter.
- **Contracts added:** ADAPTER — GitHub pre-merge signals; NEW_CAPABILITY — durable one-time
  clearance reference.
- **Authority impact:** uses ACP as-is (shadow). **GitHub writes:** none.
- **Tests:** pre-merge signals; expiry; stale-artifact rejection in shadow.
- **Acceptance:** shadow clearance matches recorded chain; denials/holds surfaced.
- **Rollback:** shadow-only. **Evidence tier:** shadow.

## Phase F — GitHub Execution Provider (controlled enforcement — MVP 1C)
- **Prerequisites:** A–E; durable audit + durable workflow persistence; chain binding (R1);
  one-time consumption (R13); tokens/webhook (R10/R11).
- **Packages:** `providers/github-execution` (new; model on `actiongate_provider/`).
- **Contracts reused:** `ExternalExecutionProvider.dispatch/observe`; DA `ExecutionIntent/Attempt/
  Record/Reconciliation`.
- **Contracts added:** PROVIDER_SPECIFIC — GitHub execution adapter.
- **Authority impact:** dispatch role only; no policy interpretation. **GitHub writes:** yes.
  **Enforcement:** yes (controlled).
- **Tests:** one exact merge op; idempotency; observation; reconciliation; §4.7 chain-proof
  fail-closed; conformance suite (execution family).
- **Acceptance:** only `EXACT_CHANGE_AUTHORIZED` + `OPERATIONALLY_CLEARED` + reconstructable chain →
  single-use dispatch; duplicate/timeout handled safely.
- **Rollback:** revoke merge credential; disable provider (returns to 1B). **Evidence tier:** enforced.

## Phase G — Merge queue
- **Prerequisites:** direct-merge (merge/squash) semantics proven.
- **Acceptance:** merge-group re-validation + derived authorization + ACP clearance of exact
  merge-group; reconcile resulting commit. **Evidence tier:** enforced.

## Phase H — Competitive Code Adjudication (optional, MVP2)
- **Prerequisites:** standard PR governance stable.
- **Packages:** `packages/capabilities/competitive-adjudication` (new).
- **Acceptance:** advisory recommendation only; §9.2 integrity controls; linked to `DecisionRecord`;
  no path to authorization. **Evidence tier:** advisory.

## Phase I — Deployment Governance (MVP3)
- **Prerequisites:** merge governance stable.
- **Acceptance:** separate artifact + environment authorization chain; build provenance / image-digest
  binding carried in ACP deployment clearance. **Evidence tier:** enforced.

## Sequencing rationale

Phases A–E add **no enforcement and no GitHub writes** — they can ship while the P0 durable/ACP/
chain prerequisites are being built. Enforcement (F) is deliberately last and gated on the P0 cluster
(`RISK_REGISTER.md`). Competitive adjudication (H) and deployment (I) are strictly later and optional.
