# Governance Contracts — Gaps & Evolution Plan (§14)

**These gaps are DOCUMENTED, not implemented in this phase.** This migration was
a pure physical extraction with zero semantic change. Every item below is a
*future contract-evolution* concern requiring its own versioned phase; none may be
"silently repaired" during a physical move (task §4). Evidence is drawn from the
current code and the two prior audits.

Legend — *Backward-compatible?* = can it be added as an optional field / additive
symbol without breaking the frozen contract; *v2?* = whether a versioned v2
contract is likely required.

## G1 — No tenant identity in neutral contracts
- **Evidence:** `ActionGovernanceRequest`, `AssertionGovernanceRequest`,
  `ExecutionDispatchRequest` carry `correlation_id` but **no `tenant_id`**. Tenant
  lives only on kernel records (`decision_governance` CER/ActionRequest).
- **Affected:** every provider consumer; multi-tenant deployments.
- **Risk:** cross-tenant ambiguity when contracts are used outside the kernel.
- **Direction:** add optional `tenant_id: str = ""` to the request envelopes.
- **Backward-compatible?** Yes (additive optional field → MINOR). **v2?** No.

## G2 — No environment identity
- **Evidence:** no `environment_id` on any neutral request/result.
- **Affected:** all; env-scoped policy/routing.
- **Direction:** add optional `environment_id: str = ""`.
- **Backward-compatible?** Yes (MINOR). **v2?** No.

## G3 — Inconsistent authority classification / advisory-vs-binding ambiguity
- **Evidence:** results carry `outcome`/`coverage`/`business_outcome` but **no
  explicit `authority_type` or `advisory|binding` field**; the meaning is implicit
  in which provider produced the result. The frozen manifest's F4–F8 invariants
  encode these meanings in *tests*, not in the *contract*.
- **Affected:** any consumer composing results from multiple families.
- **Risk:** a downstream reader cannot tell advisory from binding from the envelope
  alone.
- **Direction:** add an optional result-envelope field
  `authority: {ADVISORY|BINDING|AUTHORIZATION|CLEARANCE|EXECUTION}` +
  `required_next_step`. Must not change existing enum meanings.
- **Backward-compatible?** Yes if additive and defaulted (MINOR). **v2?** Only if
  the field is made required.

## G4 — Fragmented audit shapes
- **Evidence:** three audit shapes coexist (kernel `AuditRepository`, control-plane
  hash-chain, console in-memory). No neutral audit-reference contract in the shared
  layer.
- **Affected:** cross-capability audit correlation.
- **Direction:** a neutral `AuditRef`/`EvidenceRef` contract (later phase).
- **Backward-compatible?** Yes (new additive contract). **v2?** No (new, not a change).

## G5 — CER version fragmentation
- **Evidence:** kernel `ContextEnvelopeRecord`, `cer_v0_1/2/3`, and a console ad-hoc
  CER are three different shapes.
- **Affected:** agent runtime, console, kernel.
- **Direction:** converge on one canonical CER identity contract in a dedicated CER
  phase; **not** part of the provider-contract layer.
- **Backward-compatible?** Partially. **v2?** Likely yes for a unified CER.

## G6 — No standard error *envelope*
- **Evidence:** `ProviderError` + `FailureClass` classify errors, but there is no
  serializable *error result envelope* (code, message, retryable, correlation) for
  transport across a service boundary.
- **Affected:** any networked provider.
- **Direction:** add an optional `ErrorEnvelope` contract; keep the exception
  taxonomy unchanged.
- **Backward-compatible?** Yes (additive). **v2?** No.

## G7 — No idempotency contract
- **Status:** landed in `ugence-governance-contracts` 0.4.0 as the additive
  `contracts/idempotency.py` family (`IdempotencyScope`, `IdempotencyKey`,
  `IdempotencyDisposition`, `IdempotencyResolution`). `duplicate_of` lives on
  `IdempotencyResolution`, not on the frozen `ExecutionDispatchResult`, because the
  serialization baseline pins that dataclass byte-for-byte.
- **Evidence:** `idempotency_key` exists as a free string on action/execution
  requests, but there is **no contract** defining its semantics, scope, or a
  dedup-result field.
- **Affected:** execution/action dispatch.
- **Direction:** specify idempotency semantics + an optional `duplicate_of` result
  field.
- **Backward-compatible?** Yes (semantics + additive field). **v2?** No.

## G8 — No expiry/staleness contract
- **Status:** landed in `ugence-governance-contracts` 0.4.0 as the additive
  `contracts/validity.py` family (`Validity`, `ValidityStatus`). `stale` is derived
  at an explicit `as_of` from a `stale_after` bound, not stored.
- **Evidence:** `ActionGovernanceResult.expiry` and
  `ActionGovernanceRequest.authorization_expired` exist ad hoc; no neutral
  staleness/expiry contract shared across families.
- **Affected:** action authorization, assertion freshness.
- **Direction:** a small neutral `Validity{issued_at, expires_at, stale}` contract.
- **Backward-compatible?** Yes (additive). **v2?** No.

## G9 — No cross-product result envelope
- **Evidence:** each family has its own result shape; there is no common envelope
  carrying `module_id, module_version, policy_version, result_digest,
  correlation_id` (Audit 1 §10 called this out).
- **Affected:** multi-capability composition / a hosted control plane.
- **Direction:** an optional common `ResultEnvelope` wrapper.
- **Backward-compatible?** Yes (additive wrapper). **v2?** No.

## G10 — No product-independent workflow references
- **Evidence:** `workflow_id`/`case_id` appear only where a workflow has them; they
  are not universal (Audit 2: forcing them onto StoryGraph/Context-Min is noise).
- **Direction:** keep workflow refs **contextual**, not universal; document rather
  than add.
- **Backward-compatible?** N/A (deliberately not added). **v2?** No.

## G11 — Fields duplicated with incompatible semantics
- **Evidence:** `correlation_id` (contracts, string) vs kernel `correlation_id`
  vs `cer_v0_3` correlation — thin and not echoed on results.
- **Direction:** define one canonical correlation contract + echo it on results.
- **Backward-compatible?** Yes if additive echo. **v2?** No.

---

## Sequencing recommendation

A single **governance-contracts v0.2 / v1.1 evolution phase** can land G1, G2, G3,
G6, G7, G8, G9, G11 as **additive optional fields / new additive contracts**
(MINOR, backward-compatible) behind explicit tests. G4 and G5 (audit + CER
unification) are larger and belong to dedicated audit/CER phases. None of these
belong in a physical migration, and none were implemented here.
