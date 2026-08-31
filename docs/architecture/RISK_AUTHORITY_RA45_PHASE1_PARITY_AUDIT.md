# Risk Authority RA-4.5 — Phase 1 Semantic Parity Audit

**Status: AUDIT RESULT (analysis only — no adapters written, no production code modified).**

This document is the mandatory Phase 1 output required by
`RISK_AUTHORITY_RA45_ADAPTER_PLAN.md §7` before any RA-4.5 adapter is designed.
It compares the merged Risk Authority reference semantics against the two
canonical shipped kernels and returns a feasibility verdict.

Scope discipline: this is **not** a coding task. A field that exists on one side
and not the other is recorded as an architectural fact, never hidden behind a
default.

---

## PHASE 0 — Live provenance

| Fact | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default branch HEAD | `59bb4f2762e624d3b2efe90e3d8c555f502da687` (the merge commit) |
| PR #1396 | **Merged** (merge commit is current default HEAD) |
| Merged RA head | `16056fb0…` — verified **ancestor** of default HEAD |
| Working tree | clean |
| RA present on default? | **Yes** — `packages/risk_authority/` |

Verified package locations (structure did not shift under assumption):

- **Risk Authority (reference):** `packages/risk_authority/` — dist `ugence-risk-authority`, import `risk_authority`.
- **Production Decision Authority:** `packages/capabilities/decision-authority/` — import `ugence_decision_authority`.
- **Production ActionGate:** `packages/providers/actiongate/` — import `ugence_actiongate_provider`.
  (Top-level `actiongate_provider/` is a **logic-free compatibility facade**
  that re-exports the canonical package by object identity — not a second impl.)

Design intent read from the preserved branch `claude/risk-authority-ra45-plan`
@ `acc34e40…`: `docs/architecture/RISK_AUTHORITY_RA45_ADAPTER_PLAN.md`
(not present on default; treated as intent, not proof). Issue **#1397** (F-D)
read in full.

---

## Headline finding (read this first)

The two "kernels" RA-4.5 proposes to adapt onto are **not the same kind of
object** as the RA reference components they would replace. They enforce
**strictly less**, and the gap is architectural, not cosmetic.

- **RA `ReferenceDecisionAuthority`** issues a *machine authority grant*: a
  binding `RiskOutcome.ALLOW` carrying a per-dimension **`Scope`**, proven
  `Scope_issued ⊆ Scope_delegated`, time-bound, feeding a signed envelope.
- **`ugence-decision-authority`** is a *human/committee/policy
  **decision-of-record** and case-management* kernel. Its binding outcome is
  `{ADVANCE, HOLD, REJECT, DEFER}`, its authority holder **cannot be an AI**, it
  carries **no authority scope object**, **no scope-subset relation**, **no
  decision expiry**, **no revocation**, **no authority epoch**, and it "never
  invokes the ActionGate" (`decisions/decision.py:1-8`).

- **RA `ReferenceActionGate`** is a *cryptographic capability enforcer*: it
  verifies an Ed25519 envelope signature, time window, tenant/session binding,
  revocation and authority epoch **offline**, then matches the exact canonical
  action against the envelope scope (purpose / tools allow+deny / data allow+deny
  / destination / amount).
- **`ugence-actiongate-provider`** is an *advisory action-type policy provider*.
  Its decision is a **pure function of `action_type`** against configured
  denied/constrained/unknown sets (`core.py:141-168`). It verifies **no
  signature, no tenant** (the neutral request has no tenant field and the mapper
  hard-codes `tenant=""` — `mapping/request.py:31`), **no time/expiry** (the
  neutral contract's `authorization_expired` is a *caller-asserted bool the
  engine never reads*), **no revocation, no epoch, no scope subset, no
  amount/tools/data/destination/jurisdiction/autonomy matching**. The typed
  `maximum_amount` / `allowed_region` / `required_approval` values it can carry
  are **outputs (constraints/obligations) for a downstream executor**, not input
  checks it performs.

Consequence: you **cannot** route RA authority *through* these kernels and
preserve the RA-1→RA-4 invariants, because the kernels would enforce less than
the reference. The invariants survive **only** if RA keeps owning them (envelope
verifier + scope logic stay in RA) and the kernels are consulted as *additive,
fail-closed* gates — which is **not** the "reference port → kernel adapter"
substitution the plan (§8/§9) describes.

---

## PHASE 1 — Canonical public contracts

### Risk Authority (reference) — what it owns
- `Scope` (`domain/scope.py:24-67`): `purposes, tools_allow, tools_deny,
  data_allow, data_deny, destinations, jurisdictions, models, actors,
  max_autonomy_level:int, max_transaction_minor_units:int|None`. One shape used
  for grant, decision, and envelope.
- `subset_violations()` (`domain/scope.py:85-130`): the machine form of
  monotonicity — allow-dims subset, deny-dims superset, ceilings narrow down.
- `AuthorityGrant` + `authority_violations()` (`domain/authority.py:29-89`):
  tenant, domains, allowed_risk_classes, max_autonomy, `grantable_scope`, expiry;
  enforces `requested_scope ⊆ grantable_scope`.
- `RiskDecision` (`domain/decision.py:15-45`): `outcome:RiskOutcome`, `scope`,
  `workflow_ir_digest`, `evidence_snapshot_digest`, `model_digest`, `issued_at`,
  `expires_at`. `grants_authority` iff ALLOW / ALLOW_WITH_CONDITIONS.
- `RiskAuthorizationEnvelope` (`domain/envelope.py:47-77`): signed, `not_before`
  / `expires_at`, `scope`, `conditions`, `bindings` (digests + `authority_epoch`),
  `key_id`, `signature`.
- `CanonicalAction` (`domain/actions.py:20-43`): `tenant_id, actor_id, model_id,
  action_type, target_id, purpose, data_classes, destination,
  amount_minor_units, currency`. **No jurisdiction / autonomy field** → the F-D
  gap (#1397).
- Reference services: `ReferenceDecisionAuthority` (`services/decision_authority.py`),
  `EnvelopeIssuer` (`services/envelope_issuer.py`), `EnvelopeVerifier`
  (`services/envelope_verifier.py`), `ReferenceActionGate`
  (`integrations/actiongate.py`), `RiskEngine` (`services/risk_engine.py`).

### Production Decision Authority — what it owns
- `DecisionRecord` (`decisions/decision.py:25-43`): `outcome:DecisionOutcome
  {ADVANCE,HOLD,REJECT,DEFER}`, `authority_type`, `decided_by`, `decided_at`,
  ref-tuples, `reason_codes` (mandatory), `effective_status`,
  `supersedes_decision_id`. **No scope, no amount, no issued/nbf/expires.**
- `AuthorityContext` (`decisions/authority.py:23-39`): `authority_type`,
  `decision_scope:str` (opaque), `limits:tuple[str,...]` (opaque),
  `effective_from/until` (validated for ordering only — **never enforced against
  a clock**), `segregation_of_duties`, `required_approvals`.
- `AuthorityType` (`decisions/status.py:76-83`): HUMAN_REVIEWER, HUMAN_APPROVER,
  DELEGATED_POLICY, COMMITTEE, EXTERNAL_AUTHORITY — **no AI member by design**.
- Runtime action path: `ActionRequest` + `ContextEnvelopeRecord` (CER) →
  `ActionControlPlanePort.authorize` → `ActionAuthorizationResponse`
  (`actions/authorization.py:23-38`: `outcome:AuthorizationOutcome`,
  `constraints`, `obligations`, `expires_at`, `attempt`). Kernel does not
  adjudicate; it validates response integrity + expiry fail-closed.
- CER (`actions/cer.py:62-125`): the closest production "envelope" — tenant,
  action_type, target_system, `AuthoritySummary` (type + opaque scope string),
  `PolicyContext.jurisdiction:str`, `permitted_parameters` /
  `prohibited_parameters` / `data_classifications` / `required_controls` (opaque
  name tuples), `issued_at`/`expires_at`, **`content_hash` (plain sha256 —
  UNSIGNED)**. `is_expired` **is** enforced fail-closed.

### Production ActionGate — what it enforces
- Native `ActionGateRequest` (`core.py:71-84`): action_type, parameters(str→str),
  principal, `authority:str`, resource, policy_context, risk_context,
  evidence_refs, decision_refs, tenant, correlation/idempotency.
- Neutral `ActionGovernanceRequest`
  (`governance-contracts/.../contracts/action.py`): action_type,
  requested_parameters, actor, `authority_context:str`, target_resource,
  policy_refs, risk_context, evidence_refs, decision_refs, `authorization_expired:bool`.
  **No tenant, no scope, no signature, no structured amount/tools/data.**
- Engine decision = `action_type` lookup only (`core.py:141-168`).
  `ALLOW/DENY/ALLOW_WITH_CONSTRAINTS/UNKNOWN`; **UNKNOWN never authorizes**
  (`mapping/result.py:26-31,49-50`) — the one fail-closed axis it does own.

---

## PHASE 2 — Decision Authority parity matrix

Reference = `ReferenceDecisionAuthority` / RA `RiskDecision`+`Scope`.
Kernel = `ugence-decision-authority`.

| Dimension | RA reference | Kernel | Equivalent? | Kernel stricter? | Mapping req'd | Blocking? | Evidence |
|---|---|---|---|---|---|---|---|
| tenant binding | `RiskDecision.tenant_id`, grant tenant check | `tenant_id` on every record; access policy | ~ | no | rename | no | `authority.py:67`; DA `decision.py:27` |
| subject/actor identity | grant principal, case subject | `decided_by:str`, `ActorIdentity` | partial | no | map | no | DA `identity/provider.py` |
| model/agent identity | `model_id`, `model_digest` | **none** (only free `model_provenance` on *recommendation*) | **no** | no | — | **yes (lost)** | DA `recommendation.py:41` |
| workflow identity | `workflow_ir_digest` | `policy_refs`/`assessment_refs` (VersionedRef, not digest) | **no** | no | derive | **yes** | DA `decision.py:38` |
| policy digest | `applicable_rules`, digests | `policy_refs:VersionedRef` (id+ver, not digest) | **no** | no | derive | at-risk | DA `decision.py:38` |
| risk class | `RiskClass` on decision | **none** | **no** | no | — | reference-only | — |
| requested scope | `Scope` (10 dims) | **none** | **no** | no | — | **BLOCKING** | DA has no scope object |
| grantable scope | `grant.grantable_scope` | `decision_scope:str` + `limits:tuple[str]` (opaque) | **no** | no | — | **BLOCKING** | DA `authority.py:32,36` |
| **delegation monotonicity** `⊆` | `subset_violations` per dim | **absent** (subset only for *execution params*) | **no** | no | — | **BLOCKING** | DA search: no authority subset |
| amount/value ceiling | `max_transaction_minor_units` | **none** on authority | **no** | no | — | **BLOCKING** | — |
| allowed/denied actions | via scope tools_allow/deny | **none** | **no** | no | — | blocking | — |
| allowed/denied data | data_allow/deny | **none** on decision | **no** | no | — | blocking | — |
| destination | `destinations` | **none** | **no** | no | — | blocking | — |
| conditions | `evaluation.conditions` | `constraints`/`limits` (opaque) | partial | no | map | no | — |
| human approval | autonomy + conditions | `required_approvals`, `HUMAN_AUTHORITIES`, SoD | **kernel stricter** | **yes** | additive | no | DA `status.py:87`; `authority.py:45` |
| autonomy level | `max_autonomy_level`, grant `max_autonomy` | **none** | **no** | no | — | blocking (F-D) | — |
| jurisdiction | `jurisdictions:tuple` | `PolicyContext.jurisdiction:str` (unenforced) | **no** | no | lossy | blocking (F-D) | DA `cer.py:50` |
| issued-at | `RiskDecision.issued_at` | `decided_at` | ~ | no | rename | no | DA `decision.py:35` |
| not-before | envelope `not_before` | **none** | **no** | no | RA-owned | no | — |
| expiry | `RiskDecision.expires_at` | **none on decision** (only CER/authz downstream) | **no** | no | RA-owned | **F-B risk** | DA §5 |
| authority epoch | `bindings.authority_epoch` | **none** | **no** | no | RA-owned | blocking-if-delegated | — |
| revocation | `RevocationState` | **none** (only supersession) | **no** | no | RA-owned | blocking | DA §5 |
| decision identity | `decision_id` | `decision_id` | yes | — | direct | no | — |
| recommendation vs binding | engine advisory; DA re-derives | **advisory pinned `Literal[True]`; binding is caller-asserted, gated** | different | mixed | see F-A | — | DA `recommendation.py:46` |

**`Scope_issued ⊆ Scope_delegated`:** the kernel **cannot represent this relation.**
It has no bounded scope object and no subset operator over authority (the only
`subset` logic in the package guards *execution parameters vs authorized
parameters*, not authority scope). This is the single most important row and it
is a hard gap.

---

## PHASE 3 — F-A regression parity (forged ALLOW ⇏ bypass)

**RA fix (authoritative):** the application facade re-derives the binding
recommendation from the case's **persisted control state**, ignoring any
caller-supplied evaluation except its (only-tightening) `conditions`
(`api/dependencies.py:301-315`). `ReferenceDecisionAuthority` then maps
recommendation→outcome and only allow-family requires authority
(`services/decision_authority.py:107-131`). Regression:
`tests/adversarial/test_gate_integrity.py:66-108`.

**Kernel behaviour:**
- The binding `DecisionRecord.outcome` is **caller-supplied** to
  `record_decision(...)` and gated by authority/readiness/SoD validation — the
  kernel **does not derive it from control state** and has **no `required_controls`
  gate of its own** (controls are packed into the CER and adjudicated by the
  external control plane).
- The kernel *does* strongly separate advice from binding
  (`advisory_only:Literal[True]`, AI cannot bind) and never lets INDETERMINATE/
  malformed outcomes become approval (`OUTCOME_TO_STATUS`, response-integrity gate,
  `action_authorization_service.py:118-123`).

**Answers:**
1. Does the kernel trust a caller-supplied recommendation? It ignores
   *recommendations* for binding (they can't bind), but it **trusts the
   caller-supplied binding `outcome`** — it does not compute it.
2. Does it independently derive binding authority from control evidence? **No.**
3. Can an adapter reintroduce F-A? **Yes, easily** — if the adapter lets the
   kernel's (or caller's) disposition become the RA `RiskOutcome`, a case with a
   failed required control could be recorded ALLOW.
4. Exact adapter rule to preserve fail-closed: **the RA `RiskOutcome` MUST be
   derived by RA's own `RiskEngine` over persisted `ControlResult`s (the existing
   `api/dependencies.py:307-315` seam) BEFORE any kernel call. The kernel may only
   *further restrict* (veto → DENY/ESCALATE); it may never *upgrade* toward
   ALLOW.** The control-derivation seam stays in RA and is never delegated.

Classification: **not a blocking gap for F-A itself** (RA keeps the seam), **but
a standing trap** — the kernel offers no F-A protection for the machine-authority
case, so the adapter must be the fail-closed boundary.

---

## PHASE 4 — Decision state / expiry parity (F-B)

| RA concept | Kernel equivalent | Verdict |
|---|---|---|
| `AUTHORITY_REVIEW` precondition | `CaseStatus.READY_FOR_DECISION` + readiness eval | analogous (kernel stricter: reviews/SoD) |
| decision issuance preconditions | authorize + readiness + authority validation | analogous |
| **decision expiry** | **none on `DecisionRecord`** | **gap** |
| decision identity | `decision_id` | present |
| workflow/policy binding | `policy_refs` (ref, not digest) | weaker |

**F-B (`now > decision.expires_at → no fresh authority`):** enforced in RA at the
**envelope issuer** (`services/envelope_issuer.py:81-86`), which is RA-owned and
stays RA-owned. The kernel has no decision expiry, so it cannot enforce F-B — but
it does not need to, provided the adapter stamps `RiskDecision.expires_at` from
RA's own TTL and RA's `EnvelopeIssuer` remains the mint boundary. **F-B is
preservable, RA-owned, not kernel-derivable.** (The kernel *does* enforce CER and
authorization expiry fail-closed downstream — `cer.is_expired`,
`AuthorizationExpiredError` — a useful additive check, but not a substitute for
decision expiry.)

---

## PHASE 5 — ActionGate parity matrix

Reference = `ReferenceActionGate`. Provider = `ugence-actiongate-provider`.

| Dimension | RA reference (enforced input) | Provider | Equivalent? | Blocking? | Evidence |
|---|---|---|---|---|---|
| tenant | action==envelope==identity tenant | **dropped** (`tenant=""`) | **no** | **BLOCKING** | `integrations/actiongate.py:99-102`; `mapping/request.py:31` |
| actor | action==envelope.subject==identity | not checked (principal passed, unused for decision) | **no** | **BLOCKING** | `actiongate.py:103-106` |
| model | action==envelope==identity model | **no representation** | **no** | **BLOCKING** | `actiongate.py:107-110` |
| purpose | `action.purpose ∈ scope.purposes` | not enforced | **no** | blocking | `actiongate.py:120` |
| action type / tool | allow-set ∧ ¬deny-set | **is the only axis** (denied/constrained/unknown/default sets) | partial | — | `core.py:152-166` |
| tool allow-set | `scope.tools_allow` | no allow-set semantics (default = ALLOW) | **no** | blocking | — |
| tool deny-set | `scope.tools_deny` | `denied` set (config) — closest match | partial | — | `core.py:152` |
| data allow/deny | data_allow / data_deny match | not enforced | **no** | blocking | `actiongate.py:129-135` |
| resource/target | (F-D: not enforced in ref either) | `resource` field ignored by decision | **no** | F-D | `core.py` |
| destination | `∈ scope.destinations` | not enforced (can emit `allowed_region` *output*) | **no** | blocking | `actiongate.py:137-139` |
| amount ceiling | `≤ max_transaction_minor_units` | not enforced (can emit `maximum_amount` *output*) | **no** | blocking | `actiongate.py:141-147` |
| conditions / human approval | required_conditions, HUMAN_APPROVAL threshold | can emit `required_approval` *output* | **no** (in≠out) | blocking | `actiongate.py:149-164` |
| payload/action digest | `action.digest` binds exact action | none | **no** | blocking | `actions.py:40-43` |
| workflow/policy/model digest | `envelope.bindings` verified | none (refs only, unverified) | **no** | blocking | `envelope_verifier.py` |
| authority epoch | `revocation_state` epoch check | none | **no** | blocking | `envelope_verifier.py:82-90` |
| revocation | `RevocationState.is_revoked` | none | **no** | blocking | — |
| signature | Ed25519 verify offline | **none** (sha256 fingerprint of *output*) | **no** | **BLOCKING** | `envelope_verifier.py:53-59` |
| issued-at / nbf / expiry | envelope time window verified | **not verified** (`authorization_expired` is a caller bool, unread) | **no** | **BLOCKING** | `core.py:141-168` |
| jurisdiction | (F-D) | `PolicyContext.jurisdiction` output only | **no** | F-D | — |
| autonomy | (F-D) | **no representation** | **no** | F-D | — |

**Critical question — can the provider express every restriction the envelope may
carry?** **No.** The neutral request contract has no tenant, no scope, no
signature, no structured amount/tools/data, and the engine decides on
`action_type` alone. Even a richer *remote* engine is capped by the contract,
which cannot carry the RA scope. The provider's typed controls are **emitted
outputs**, not enforced inputs.

---

## PHASE 6 — F-D specific analysis (#1397)

For each dimension: does production ActionGate **represent** it? **enforce** it?
**map losslessly**?

| Dimension | Represented? | Enforced against a presented action? | Lossless map? | Closes F-D without extending `CanonicalAction`? |
|---|---|---|---|---|
| resource / target | Yes (`resource` / `target_system`) | **No** (ignored by the decision) | No | **No** |
| jurisdiction | Partial (`PolicyContext.jurisdiction:str`, single) | **No** (only emittable as `allowed_region` output) | No (set→string) | **No** |
| autonomy | **No** (absent everywhere) | **No** | **No** | **No** |

**Conclusion:** `ugence-actiongate-provider` does **not** already provide
suitable jurisdiction / autonomy / resource **enforcement**. It has *slots* for
resource and jurisdiction but treats them as opaque/emit-only, and autonomy is
absent. Therefore the §12 ordering question is answered: **F-D cannot be closed
by mapping onto the production provider.** Issue #1397's proposed
`CanonicalAction` extension + `ReferenceActionGate` checks remain necessary and
correct. (No factual correction to #1397 is needed — it is accurate.)

---

## PHASE 7 — Envelope / authorization artifact compatibility

**What the provider expects:** a neutral `ActionGovernanceRequest` (opaque
strings) → native `ActionGateRequest`. It does **not** accept, parse, or verify a
`RiskAuthorizationEnvelope`.

- Can the RA envelope pass through directly? **No.**
- Must it be translated? Yes — and translation is **lossy**: scope, signature,
  time, revocation, epoch, amount, tools/data have no destination fields.
- Does the provider require its own signed artifact? **No** — it requires nothing
  signed; the platform's CER is **unsigned** (`content_hash` = plain sha256).

**Trust-boundary reality (who verifies what):**

```
RiskAuthorizationEnvelope (Ed25519-signed, scoped, time-bound, epoch-bound)
        │
        ▼
   KernelActionGateAdapter
        │   signature  →  ONLY RA EnvelopeVerifier can verify (kernel cannot)
        │   tenant     →  ONLY the adapter (provider drops tenant)
        │   time/nbf/exp → ONLY RA EnvelopeVerifier (provider ignores)
        │   revocation/epoch → ONLY RA RevocationState (kernel has neither)
        │   scope match (purpose/tools/data/dest/amount) → ONLY RA scope logic
        │   action_type policy → delegated to provider (its sole competency)
        ▼
   ugence-actiongate-provider  →  action_type policy → ALLOW/DENY/CONSTRAINTS/UNKNOWN
```

**Duplicated checks:** essentially none — the provider duplicates *nothing* RA
does. **Missing checks:** *everything* authority-critical. Missing checks are not
acceptable, so **every RA verification must remain in the adapter/RA layer**; the
provider can only be an *additional* action-type veto. This is an additive
composition, not a substitution.

---

## PHASE 8 — Signature / crypto ownership

- RA: pure-Python **Ed25519 (RFC 8032)** signing + offline verify behind
  `SigningKey`/`VerifyKey`/`KeyRing` (`crypto/signing.py`, `crypto/keys.py`),
  canonical bytes (`crypto/canonical.py`), `sha256:` digests (`crypto/hashing.py`).
- Production Decision Authority: **no signing** — only `canonical_hash` (unsigned
  content hashing).
- Production ActionGate: **no signing, no verification** — sha256 JSON
  *fingerprint of its own result* only.

**Answers:**
- Who should own production signing in RA-4.5? **RA** — it is the only component
  that signs or verifies anything. Keep the `SigningKey`/`VerifyKey` abstraction;
  a future KMS/HSM backend slots behind it (plan §13) independently.
- Can RA mint and the provider verify? **No** — the provider cannot verify a
  signature at all. RA must both mint **and** verify (via the adapter reusing
  `EnvelopeVerifier`).
- Should Decision Authority produce the canonical signed artifact? **No** — it has
  no signing and its `DecisionRecord`/CER carry a different, unsigned shape.
- Incompatible canonicalization/digest formats? RA `sha256:` canonical-bytes vs
  DA `canonical_hash` vs ActionGate result fingerprint are **three unrelated,
  non-interoperable** schemes. There is **no competing *signed* artifact**, so
  there is no re-signing collision — but equally, **no kernel can validate RA's
  signature binding**, so signature verification cannot be delegated.
- Would translation invalidate signature binding? Any lossy translation to the
  neutral request **discards** the signed payload; the provider never checks it,
  so binding is simply **not enforced** on that side. The adapter must verify the
  RA signature **before** consulting the provider.

**Flag:** the RA envelope and the production CER **cannot be safely
translated into one another without re-authorizing** — different fields,
different (unsigned vs signed) trust models. Do not attempt to convert one signed/
hashed artifact into the other.

---

## PHASE 9 — Field mapping tables

### `RiskDecisionCase` / RA decision → `ugence-decision-authority`

| RA field | Kernel target | Class |
|---|---|---|
| `tenant_id` | `tenant_id` | direct (rename) |
| `case_id` | `decision_case_id` | direct |
| `RiskOutcome` (ALLOW/DENY/ESCALATE) | `DecisionOutcome` (ADVANCE/HOLD/REJECT/DEFER) | **not representable** (category mismatch) |
| `Scope` (10 dims) | — | **not representable** |
| `grantable_scope` / `⊆` | `decision_scope:str` + `limits` | **not representable** (opaque) |
| `max_transaction_minor_units` | — | **not representable** |
| `jurisdictions:tuple` | `PolicyContext.jurisdiction:str` | normalized-lossy |
| `max_autonomy_level` | — | **not representable** |
| `model_id` / `model_digest` | — (recommendation `model_provenance` only) | **not representable** on binding |
| `workflow_ir_digest` | `policy_refs`/`assessment_refs` (VersionedRef) | derived-lossy (id+ver ≠ digest) |
| `issued_at` | `decided_at` | direct |
| `expires_at` | — | **must remain RA-owned** |
| `authority_epoch` | — | **must remain RA-owned** |
| — | `authority_type`, SoD, `required_approvals` | **production-only stronger** (human governance) |

### `RiskAuthorizationEnvelope` + `CanonicalAction` → ActionGate provider request

| RA field | Provider target | Class |
|---|---|---|
| `action.action_type` | `action_type` | direct |
| `tenant_id` | `tenant` | **must remain outside adapter** (provider drops it) |
| `subject`/`actor_id` | `principal`/`actor` | carried, **not enforced** |
| `model_id` | — | **not representable** |
| `scope.purposes/tools/data/destinations` | — | **not representable** (→ enforce in adapter) |
| `scope.max_transaction_minor_units` | — (only emittable as output) | **not representable** |
| `signature`/`key_id` | — | **not representable** (verify in adapter) |
| `not_before`/`expires_at` | — (`authorization_expired` bool unread) | **not representable** (verify in adapter) |
| `bindings.authority_epoch` / revocation | — | **not representable** (check in adapter) |
| `conditions.*` | — (only emittable as `required_approval` output) | **not representable** as input |

No authority-critical field admits a "best-effort" mapping — every one above is
either direct-trivial or not-representable. There is no safe hidden default.

---

## PHASE 10 — Error / deny semantics

| Concept | RA | DA kernel | ActionGate provider |
|---|---|---|---|
| DENY (policy) | `RiskOutcome.DENY` / `ActionGateDecision.DENIED` | `DecisionOutcome.REJECT` (case) / `AuthorizationOutcome.DENIED` | `DENY`→`DENIED` |
| ALLOW | `ALLOW` / `AUTHORIZED` | `ADVANCE` / `AUTHORIZED` | `ALLOW`→`AUTHORIZED` |
| conditional | `ALLOW_WITH_CONDITIONS` / (via conditions) | `AUTHORIZED_WITH_CONSTRAINTS` (≥1 constraint required) | `ALLOW_WITH_CONSTRAINTS` |
| indeterminate/unknown | (RA denies; no ALLOW leak) | `INDETERMINATE` (retryable, never allow) | `UNKNOWN`→`INDETERMINATE` (never authorizes) |
| infra ERROR | exception → fail closed | provider exc → `AuthorizationSubmissionError` (never approval) | native exc **translated**, never escapes as allow |
| expired | envelope/decision expiry → DENY | `EXPIRED` (retryable, never allow) | `EXPIRED` enum exists; **engine never emits it** |

**`ERROR ⇏ ALLOW`:** holds on all three sides. Both kernels are fail-closed on
the *disposition* axis (UNKNOWN/INDETERMINATE/error never become AUTHORIZED —
`mapping/result.py:49-50`, `OUTCOME_TO_STATUS`). Infra failure is **not** conflated
with policy denial (distinct exceptions/outcomes). Proposed adapter disposition
map (fail-closed): provider `UNKNOWN`/`INDETERMINATE`/any translated error →
**RA DENY** (not ESCALATE, since the provider carries no authority basis to
escalate on); provider `DENY` → RA DENY; provider `ALLOW`/`ALLOW_WITH_CONSTRAINTS`
→ RA proceeds **only if** RA's own envelope+scope checks already passed.

---

## PHASE 11 — Determinism / reason codes

- RA reason codes: rich, structured deny reasons (`reason_codes` tuple per
  failed dimension). DA: catalog `ReasonCode` (mandatory, in-catalog validated).
  Provider: coarse `policy_denied` / `policy_allow` / `policy_unknown`.
- Determinism: all three are deterministic pure functions of input+config.
- **Parity assertion level:** compare **disposition (ALLOW/DENY) + the fact of
  scope reduction / constraint presence + decision identity binding**. Do **not**
  assert reason-code or error-string equality — the vocabularies are unrelated and
  no contract promises them equal. Where production is *deliberately stricter*
  (SoD, required approvals, action-type deny), assert `reference=ALLOW ⇒
  production ∈ {ALLOW, DENY}` (stricter allowed), never the reverse.

---

## PHASE 12 — Differential test plan (design only)

Run identical scenarios through **reference stack** (`ReferenceDecisionAuthority`
+ `ReferenceActionGate`) vs **production-composition stack**
(`KernelDecisionAuthorityAdapter` + `KernelActionGateAdapter`). Assertion level:
disposition + scope-reduction + binding identity (per Phase 11).

| Scenario | Reference | Expected production | Parity | Stricter-OK? |
|---|---|---|---|---|
| `crm.read` in scope | ALLOW | ALLOW | equal | — |
| `refund.prepare` $3,000 ≤ ceiling | ALLOW | ALLOW | equal | — |
| `refund.prepare` $6,000 > ceiling | DENY (amount) | **DENY only if adapter enforces amount** | equal | — |
| `refund.execute` not in tools_allow | DENY | DENY (adapter) | equal | — |
| `email.external` bad destination | DENY | DENY (adapter) | equal | — |
| wrong tenant | DENY | DENY (adapter — provider drops tenant) | equal | — |
| wrong actor | DENY | DENY (adapter) | equal | — |
| wrong model | DENY | DENY (adapter) | equal | — |
| wrong target/resource | (ref ALLOWs — F-D) | DENY only after #1397 | **documented divergence** | yes |
| wrong jurisdiction | (ref ALLOWs — F-D) | DENY only after #1397 | documented | yes |
| autonomy too high | (ref ALLOWs at gate — F-D) | DENY only after #1397 | documented | yes |
| expired decision | DENY (issuer) | DENY (RA issuer) | equal | — |
| expired envelope | DENY (verifier) | DENY (adapter verifier) | equal | — |
| revoked envelope | DENY | DENY (adapter) | equal | — |
| stale epoch | DENY | DENY (adapter) | equal | — |
| tampered payload | DENY (digest) | DENY (adapter) | equal | — |
| tampered signature | DENY (verify) | DENY (adapter) — provider cannot detect | equal | — |
| wrong workflow digest | DENY | DENY (adapter) | equal | — |
| wrong policy digest | DENY | DENY (adapter) | equal | — |
| failed mandatory control | DENY (re-derived) | DENY (RA RiskEngine seam) | equal | — |
| duplicate FAIL+PASS control | DENY (F-E) | DENY (RA controls) | equal | — |

**Note the pattern:** every "production DENY" above is annotated *"(adapter)"* —
because the production kernels themselves would ALLOW or ignore these. The
differential suite would pass **only if the adapter re-implements RA enforcement**,
proving the kernels are not the enforcers.

---

## PHASE 13 — Package architecture feasibility

- `risk_authority` stdlib-only leaf? **Yes** — verified zero third-party runtime
  imports; kernels do **not** import `risk_authority`.
- Adapters entirely outside the leaf? **Yes** — required by plan §2.
- Dependency cycles? **None** — DA and ActionGate do not import each other or RA.
  Integration package → all three (one-way).
- Kernels depend on RA or each other? **No.**
- Platform-freeze violation? None from a *new* integration package that only
  imports published public APIs.

**Feasible.** Tentative location (mark tentative): `packages/integration/
risk-authority-runtime/` (import `ugence_risk_authority_runtime`), reconciled with
the monorepo `packages/…` convention at kickoff. Naming is **not** finalized.

---

## PHASE 14 — Decision Authority adapter verdict

**BLOCKED_BY_SEMANTIC_GAP** (for the plan-§8 design where the kernel owns the
binding ruling).

Reasons: `ugence-decision-authority` cannot represent or enforce the RA
authority-critical semantics — **authority `Scope`**, the **`Scope_issued ⊆
Scope_delegated` monotonicity relation**, **amount ceiling**, **model identity on
the binding**, **decision expiry**, **revocation**, and **authority epoch** are
all absent; its binding outcome vocabulary (ADVANCE/HOLD/REJECT/DEFER, AI-excluded)
is a category mismatch with ALLOW+scope, and its binding outcome is caller-asserted
rather than control-derived.

**Smallest path that unblocks (recommended composition — not the §8 substitution):**
RA **retains** `ReferenceDecisionAuthority`'s scope/monotonicity/expiry logic as
the authority-scope issuer; the kernel is consulted **only** as a fail-closed
*human/committee/delegated-policy governance veto* (its genuine strength: SoD,
required approvals, non-AI authority). Required upstream/precondition work:
(a) the leaf-safe DI seam (plan §6); (b) an explicit architecture decision that
the platform has **no** machine-authority-scope issuer and RA remains it.

---

## PHASE 15 — ActionGate adapter verdict

**BLOCKED_BY_SEMANTIC_GAP** (for the plan-§9 design where the provider is the
enforcement boundary).

Reasons: the neutral request contract carries **no tenant, no scope, no
signature, no structured amount/tools/data**, and the engine decides on
`action_type` alone. It verifies **none** of signature / time / revocation /
epoch / tenant / actor / model / purpose / tools / data / destination / amount —
i.e. it enforces strictly less than `ReferenceActionGate`. **F-D** (resource /
jurisdiction / autonomy) is likewise unsolved: resource and jurisdiction are
opaque/emit-only, autonomy is absent.

**Feasible-with-explicit-mapping only as an *additive* composition:** the adapter
verifies the RA envelope (reuse `EnvelopeVerifier`) and matches scope itself
(reuse RA scope logic), then **additionally** consults the provider for the
`action_type` policy question, combining fail-closed (deny if either denies;
provider `UNKNOWN`→deny). This weakens nothing but makes the provider an *extra*
gate, not the enforcer.

---

## PHASE 16 — Overall RA-4.5 verdict

# RA45_BLOCKED

Per the plan's own rule ("`RA45_BLOCKED` if a production kernel cannot represent
or enforce an RA authority-critical semantic"): **both** kernels cannot represent
or enforce multiple authority-critical semantics — authority scope + `⊆`
monotonicity, decision expiry, revocation, authority epoch, offline signature
verification, and exact-action scope matching (tenant/actor/model/purpose/tools/
data/destination/amount). The plan-as-written (§8/§9: reference ports → kernel
adapters, kernels owning the ruling/enforcement) is blocked because it would
**weaken** every one of those invariants.

This is exactly the outcome the audit exists to surface **before** coding: RA-4.5
is **not** a straightforward integration PR. The block is architectural, not a
one-line contract tweak.

**Convertible to `RA45_READY_WITH_PRECONDITIONS`** if — and only if — the
composition is re-scoped so that **Risk Authority remains the authoritative owner
of authority scope, monotonicity, envelope signing/verification, expiry,
revocation and epoch**, and the production kernels are wired as **additive,
fail-closed** collaborators:
- `ugence-decision-authority` → human/committee/delegated-policy governance veto
  (never upgrades toward ALLOW; never supplies the scope);
- `ugence-actiongate-provider` → supplementary `action_type` policy veto behind a
  full RA envelope verification + scope match.

Preconditions for that re-scoped path:
1. Architecture decision: RA is (and stays) the platform's machine-authority-scope
   issuer + capability-envelope enforcer; the kernels are additive gates. Update
   the plan's §8/§9 framing from "substitution" to "additive composition."
2. Leaf-safe DI seam (plan §6) — `RiskAuthorityApplication(decision_authority=,
   action_gate=)` — adding no dependency to the leaf.
3. F-D remains a separate PR (#1397: extend `CanonicalAction` + `ReferenceActionGate`);
   the production provider does **not** close it.
4. Differential suite asserts disposition + scope-reduction + binding identity
   only (Phase 11), with the three F-D rows marked documented-divergence until
   #1397 lands.

---

## PHASE 17 — Final report

**Provenance.** Default HEAD `59bb4f27` = merge commit; PR #1396 **merged**; RA at
`packages/risk_authority/`; Decision Authority at
`packages/capabilities/decision-authority/`; ActionGate at
`packages/providers/actiongate/`. Working tree clean.

**Decision Authority parity.** Kernel is a human/committee decision-of-record +
case system. No authority scope, no `⊆`, no amount, no model-on-binding, no
decision expiry, no revocation, no epoch; binding outcome is caller-asserted.
Verdict: **BLOCKED_BY_SEMANTIC_GAP** for substitution; feasible only as additive
human-governance veto.

**ActionGate parity.** Provider decides on `action_type` alone; verifies no
signature/tenant/time/scope/amount; typed controls are emit-only outputs.
Verdict: **BLOCKED_BY_SEMANTIC_GAP** for substitution; feasible only as additive
`action_type` veto behind RA's own verification.

**F-D conclusion.** Production ActionGate does **not** already solve resource,
jurisdiction, or autonomy: resource/jurisdiction are opaque/emit-only (not
enforced against a presented action), autonomy is absent. #1397 stands; F-D needs
a `CanonicalAction` extension, not a provider mapping.

**Crypto/artifact conclusion.** Neither kernel signs or verifies signatures (DA
uses unsigned `canonical_hash`; ActionGate uses an output fingerprint). Envelope
signature/time/revocation/epoch verification must remain **RA-owned**. The RA
envelope and the production CER **cannot be translated without re-authorizing**;
there is no shared signed format, so no re-sign collision — but no delegation of
signature verification is possible either.

**Blocking gaps (real, authority-critical).**
1. DA: no authority `Scope` and no `Scope_issued ⊆ Scope_delegated` relation.
2. DA: no decision expiry / revocation / authority epoch.
3. DA: binding outcome caller-asserted, not control-derived (F-A trap for the
   adapter).
4. ActionGate: no signature/tenant/time/scope/amount enforcement; `action_type`
   only.
5. ActionGate: F-D (resource/jurisdiction/autonomy) unsolved.

**Adapter package recommendation (tentative).**
`packages/integration/risk-authority-runtime/` — import
`ugence_risk_authority_runtime`. One-way deps → all three packages; no cycles;
leaf stays stdlib-only. Naming tentative, reconcile at kickoff.

**Differential test plan.** 21-row matrix (Phase 12); assert disposition +
scope-reduction + binding identity; three F-D rows are documented divergences
until #1397; every production DENY is adapter-enforced (proving the kernels are
not the enforcers).

**Overall verdict:** **RA45_BLOCKED** (against the plan as written) — convertible
to **RA45_READY_WITH_PRECONDITIONS** under the re-scoped additive composition
above.

**Next action.** Do **not** start writing §8/§9 substitution adapters. Take the
architecture decision first (precondition 1): confirm that Risk Authority remains
the platform's machine-authority-scope issuer and capability-envelope enforcer,
with `ugence-decision-authority` and `ugence-actiongate-provider` wired as
additive fail-closed vetoes. Once that decision is recorded and the leaf-safe DI
seam (precondition 2) is agreed, RA-4.5 can proceed as an *additive-composition*
integration (not a substitution), and only then should adapter code begin.
