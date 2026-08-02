# Decision Authority & CER Mapping — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4.3, §4.6, §6, §8).
> Verified against live code at commit `3ec11e4e`.

## 1. Who makes the binding decision, and how it is recorded

An **authorized actor** makes the merge decision. **Decision Authority validates and records it**
using the existing `DecisionRecord`; it does not autonomously approve code.

Flow — `CaseDecisionService.record_decision` (`services/case_decision_service.py:77`):
1. refuse if case is in a terminal status;
2. **authenticate + authorize** the actor via `authorize_case_action(..., MAKE_DECISION)`
   (`services/_case_authz.py:25` → `identity_provider.authenticate`);
3. structural readiness (`CaseValidationService.evaluate_decision_readiness`);
4. **authority validation** (`validate_authority`, `case_validation_service.py:105`) — see §3;
5. build optional `OverrideRecord`; construct the immutable `DecisionRecord`
   (`supersedes_decision_id` set to the prior decision); emit audit events.

## 2. `DecisionRecord` mapping (§4.3 confirmed — no `MergeDecisionRecord`)

`DecisionRecord` (`decisions/decision.py:25`) — immutable (`frozen=True, extra="forbid"`):

| Design need | Field | Notes |
|---|---|---|
| selected candidate / adjudication recommendation | `recommendation_refs: tuple[VersionedRef,...]` | ✅ |
| TAP / CI / security assessments | `assessment_refs: tuple[VersionedRef,...]` | ✅ |
| repository policies | `policy_refs: tuple[VersionedRef,...]` | ✅ free versioned refs |
| decision reasons | `reason_codes: tuple[ReasonCode,...]` (required) | ✅ but `ReasonCode` is a **closed enum** |
| override / exception | `override_record_id: Optional[str]` | ✅ (+ `OverrideRecord`) |
| supersession | `supersedes_decision_id` + `effective_status: EffectiveStatus` | ✅ |
| authorized actor | `decided_by: str` + `authority_type: AuthorityType` | actor is a bare principal id; no embedded `ActorIdentity` |
| tenant isolation | `tenant_id: str` | ✅ |

Findings:
- **No `content_hash` / `compute_hash()`** on `DecisionRecord` — immutability is structural only.
  For a tamper-evident chain, rely on CER `content_hash` and the durable audit backend
  (see `DURABLE_AUDIT_AND_RECONSTRUCTION.md`).
- `AuthorityType` (`decisions/status.py:76`) = `HUMAN_REVIEWER · HUMAN_APPROVER · DELEGATED_POLICY ·
  COMMITTEE · EXTERNAL_AUTHORITY` — **no AI member**; AI structurally cannot decide.
- **Result: Code Governance needs no product-specific decision record.** Preferred outcome (no
  duplicate `MergeDecisionRecord`) is achievable.

## 3. Roles, segregation of duties, author/approver conflict

- Roles are **not a first-class type**. Authority is `AuthorityType` + `AuthorityContext`
  (`decisions/authority.py:23`), which carries **`segregation_of_duties: bool=False`** and
  `required_approvals: int=0`.
- SoD / author≠approver is enforced in `validate_authority` (`case_validation_service.py:138`):
  `if authority.segregation_of_duties and decided_by in recommendation_authors → SEGREGATION_OF_DUTIES`.
- **Caveat:** SoD is enforced **only when `segregation_of_duties` is explicitly True** (False by
  default). Code Owners / security-approver requirements are **product policy** that must set
  `segregation_of_duties=True` and `required_approvals` and map GitHub roles onto `AuthorityType`.
- AI-as-decider and human-authority-without-human are rejected (`AI_CANNOT_DECIDE`,
  `HUMAN_AUTHORITY_REQUIRES_HUMAN`).

## 4. Overrides, exceptions, and decision invalidation

- `OverrideRecord` (`decisions/override.py:25`) carries `final_outcome`, `authorized_by`,
  required `reason_codes`, `permitting_policy_ref`, and reference to the original recommendation or
  policy default. Break-glass (design §16.6) maps here via `override_record_id`.
- **Invalidation when the patch changes: not automatic.** There is no content-hash watcher that
  invalidates a live `DecisionRecord`. Mechanisms: manual/append-only supersession via
  `supersedes_*` + status enums; `ReasonCode.STALE_EVIDENCE` exists but nothing computes it; CER /
  authorization fail closed on expiry. **The Workflow Service must trigger supersession** on any
  patch/head/base/policy change (see `merge_identity_schema.json` invalidation rules).

## 5. Policy versions without changing Decision Authority contracts

**Yes — supported today.** `policy_refs` are free `VersionedRef` (`decisions/subject.py:30`; `kind`
"never interpreted"), present on `DecisionRecord`, `RecommendationRecord`, `DecisionCase`,
`ActionRequest`, and `PolicyContext`. A product may reference any repository policy id + version
without a contract change. **However**, `ReasonCode` is a closed enum and all core contracts are
`extra="forbid"` — a new reason code or custom typed metadata **would** require a Decision Authority
contract change. Prefer `policy_refs` and existing reason codes.

## 6. CER mapping (§4.6, §8)

`ContextEnvelopeRecord` (cer.v1, `actions/cer.py:62`) — a **minimized governance context, not an
execution command**.

| Design need | CER field | Direct? |
|---|---|---|
| DecisionRecord ID | `decision_id` (+ `decision_context.decision_id`) | ✅ |
| repository identity | `target_system` (string) | partial (opaque string) |
| pull-request identity | — | ✗ no field |
| source/head SHA | — | ✗ (name only in `permitted_parameters`) |
| base SHA | — | ✗ |
| target branch | — | ✗ |
| merge method | — | ✗ |
| expected merge tree | — | ✗ |
| merge-group SHA | — | ✗ |
| permitted parameters | `permitted_parameters: tuple[str,...]` | ✅ **names only** |
| prohibited parameters | `prohibited_parameters: tuple[str,...]` | ✅ names only |
| required controls | `required_controls: tuple[str,...]` | ✅ names only |
| expiry | `expires_at` | ✅ |
| tenant | `tenant_id` | ✅ |
| action request ID | `action_request_id` | ✅ |
| policy references | `policy_context.policy_refs` (`VersionedRef`) | ✅ |
| content hash | `content_hash` (SHA-256) | ✅ |

**Critical structural fact:** `permitted_parameters` / `prohibited_parameters` / `required_controls`
are `tuple[str,...]` — parameter/control **names**, not key→value data. The CER has **no generic
metadata/payload dict** (`extra="forbid"`). So the exact merge-artifact **values** (specific SHAs,
merge-tree digest, merge-group SHA) have **no typed home in the CER**.

### Where the exact values live (no CER schema change required)

The three-way separation the design demands is expressible today:
- **decision evidence** → `DecisionRecord` (refs);
- **governance context** → CER (names the permitted parameter keys + required controls, binds
  decision/tenant/policy/expiry, `content_hash`);
- **execution command** → `ExecutionDispatchRequest.parameters` (later).

The **exact values** ride in `ActionRequest.requested_parameters` (`dict[str,str]`, has
`parameters_hash()`/`content_key()`) and in the neutral `ActionGovernanceRequest.requested_parameters`
(`Mapping[str,str]`). The `CERBindingService` (`services/cer_binding_service.py:66`) sets CER
`permitted_parameters` from the request's parameter **keys**, `prohibited_parameters` from
`mapping.prohibited_fields`, `required_controls` from `mapping.required_context_fields`, then stamps
`content_hash`. The product **`ExactChangeAuthorization` envelope** pairs the CER (names + hash +
expiry) with the `ActionGovernanceRequest` (values) and the `ActionGovernanceResult.fingerprint`,
and takes its own content hash over the values. See `ACTIONGATE_AND_ACP_MAPPING.md` and
`EXACT_MERGE_IDENTITY.md`.

### Classification of the missing representation

| Missing representation | Classification |
|---|---|
| exact SHA / merge-tree / merge-group **values** | **product-level envelope** (via `requested_parameters` + `ExactChangeAuthorization`) — **not** a CER schema change |
| naming which parameters are permitted / required controls | already in CER (`permitted_parameters`/`required_controls`) |
| a value-carrying typed CER field | **unnecessary duplication** — do not add; values belong in the action request/envelope |

**Verdict (resolves design open question §17.3):** the current CER surface is **sufficient** to
express the exact-change constraints via existing fields + the product envelope. **No CER version
change (`cer.v2`) is required for MVP.** If a future need arises to bind values *inside* the CER
hash itself (e.g. regulatory requirement that the CER alone reconstruct the exact artifact), that
would be the smallest justified change — a new `cer.v2` adding a typed `bound_parameters` map — and
must be owned by Decision Authority, not the product. It is **not** needed now.
