# Risk Authority RA-4.5 — Governance Composition Plan (Corrected)

**Status: DESIGN / CORRECTED — READY FOR APPROVAL. NOT IMPLEMENTED.**

This document is the **corrected** RA-4.5 architecture. It supersedes
[`RISK_AUTHORITY_RA45_ADAPTER_PLAN.md`](./RISK_AUTHORITY_RA45_ADAPTER_PLAN.md)
(the "substitution adapter" plan), which was disproven by the mandatory Phase 1
semantic parity audit
[`RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md`](./RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md).

Scope discipline: this is a **design / documentation** task only.
**No production code, no adapters, and no RA-5 work are produced here.** No PR is
opened. This document exists so the corrected architecture can be **approved
before** any implementation begins.

> **Why this correction exists.** The original RA-4.5 plan assumed the shipped
> kernels were production-equivalent replacements for the Risk Authority
> reference components, reachable by swapping them in behind
> `DecisionAuthorityPort` / `ActionGatePort`. The parity audit proved that
> assumption **false**: the kernels enforce *strictly less* and cannot represent
> RA's authority-critical semantics. Routing RA authority *through* them would
> **weaken** every RA-1→RA-4 invariant. This plan replaces substitution with
> **additive, fail-closed governance composition**.

---

## 0. Provenance (independently confirmed)

| Fact | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default branch HEAD | `59bb4f2762e624d3b2efe90e3d8c555f502da687` (the PR #1396 merge commit) |
| PR #1396 | **Merged** (`merged: true`, merged 2026-08-10; base `fcd135c`, head `16056fb0`) |
| Merged RA head | `16056fb0…` — verified ancestor of default HEAD |
| Working tree at correction start | clean |
| RA present on default | **Yes** — `packages/risk_authority/` |
| Production Decision Authority | `packages/capabilities/decision-authority/` (import `ugence_decision_authority`) |
| Production ActionGate | `packages/providers/actiongate/` (import `ugence_actiongate_provider`) |

**Direct-inspection corroboration of the audit (this correction re-verified the
load-bearing claims against current code, per the audit's own standard "unless
direct code inspection disproves a claim"):**

- `Scope` (`domain/scope.py:25-43`) carries all machine-authority dimensions:
  `purposes, tools_allow, tools_deny, data_allow, data_deny, destinations,
  jurisdictions, models, actors, max_autonomy_level:int,
  max_transaction_minor_units:int|None`. **Confirmed.**
- `DecisionAuthorityPort` (Protocol) and `ReferenceDecisionAuthority` exist
  (`services/decision_authority.py:52,76`); `ActionGatePort` (Protocol) and
  `ReferenceActionGate` exist (`integrations/actiongate.py:42,60`). **Confirmed.**
- `CanonicalAction` (`domain/actions.py:21`) fields are `tenant_id, actor_id,
  model_id, action_type, target_id, purpose, data_classes, destination,
  amount_minor_units, currency` — **no `jurisdiction`, no `autonomy` field**
  (the F-D gap, #1397). **Confirmed.**
- Production DA `DecisionOutcome` = `{ADVANCE, HOLD, REJECT, DEFER}`
  (`decisions/status.py:67-73`); `AuthorityType` docstring: *"Who may bind a
  decision. Deliberately excludes any AI model."* **Confirmed.**
- Production ActionGate `evaluate()` decides purely on `request.action_type`
  against `denied / unknown / constrained / default` sets (`core.py:141-168`);
  its `tenant` is hard-coded `""` (`mapping/request.py:31`); its typed
  `constraints / obligations / expiry_seconds` are **outputs**, not verified
  inputs. **Confirmed.**

**Divergence between audit and code: none found.** The parity audit is therefore
treated as authoritative evidence for this correction.

---

## 1. Corrected authority model — canonical ownership boundaries

The corrected model draws one hard line: **the machine-authority boundary.**
Above it, Risk Authority is the sole issuer of executable machine capability.
Below it, governance inputs may **subtract** authority but may never **add** it.

### 1.1 Decision Authority — *human / committee / organizational governance*

**Role:** organizational decision-of-record. Outcomes: `ADVANCE`, `HOLD`,
`REJECT`, `DEFER`. Authority holder is a human, committee, or delegated policy —
**never an AI** (`AuthorityType` excludes AI by construction).

**It MAY:** impose an organizational veto; require human/committee approval
(SoD, `required_approvals`); provide governance evidence and reason codes;
constrain downstream machine authority (tighten only).

**It MUST NOT:** create machine execution authority beyond Risk Authority; supply
or replace an RA `Scope`; provide the `Scope_issued ⊆ Scope_delegated` relation;
mint a `RiskAuthorizationEnvelope`; weaken or upgrade an RA `DENY`; extend an RA
expiry.

*Genuine strength (why it is worth composing):* segregation of duties, required
human approvals, and non-AI authority binding — governance semantics RA does not
itself model.

### 1.2 Risk Authority — *machine capability authority (owner)*

**Role:** the source of executable machine capability authority. **This is the
correction's fixed point: the platform has no other machine-authority-scope
issuer, and RA remains it.**

RA owns, and continues to own end-to-end:

- control-derived machine authority (`RiskEngine` over persisted `ControlResult`s);
- delegation monotonicity `Scope_envelope ⊆ Scope_decision ⊆ Scope_grant`
  (`subset_violations`, `authority_violations`);
- the signed authorization envelope (`RiskAuthorizationEnvelope`, Ed25519);
- `not_before` / `expires_at` validity windows;
- revocation (`RevocationState`);
- authority epoch (`bindings.authority_epoch`);
- tenant / actor / model binding;
- exact machine-authority scope semantics (purpose / tools allow+deny / data
  allow+deny / destination / amount ceiling).

### 1.3 ActionGate provider — *supplementary action-policy governance*

**Role:** an additional action-type policy gate. Its sole competency is an
`action_type` lookup against `denied / constrained / unknown / default` sets,
with `UNKNOWN` never authorizing (its one fail-closed axis).

**It MAY:** contribute action-type policy constraints; add extra deny/veto
conditions; emit policy-derived restrictions (`maximum_amount`, `allowed_region`,
`required_approval`) as **tightening** obligations.

**It MUST NOT:** validate away RA's signature requirement; replace envelope
verification; upgrade an RA `DENY`; create scope RA did not authorize; be treated
as having verified tenant/actor/model/time/amount (it verifies none of them).

### 1.4 Exact-action enforcement — *RA-owned*

Per current code, exact-action enforcement is **RA-owned** and stays RA-owned.
`ReferenceActionGate` (`integrations/actiongate.py`) verifies the signed envelope
(via `EnvelopeVerifier`) and matches the exact `CanonicalAction.digest` against
envelope scope. **The production provider cannot perform this** — it carries no
signature, no scope, no tenant, no amount, and decides on `action_type` alone.

Therefore the canonical exact-action matcher/verifier is **the RA envelope
verifier + RA scope logic**, invoked from the integration package by *reusing*
`EnvelopeVerifier` and RA scope checks — **not** delegated to any kernel. (Note:
the *name* `ActionGate` is shared by two different objects — RA's cryptographic
enforcer and the provider's action-type policy engine. This plan keeps them
distinct: RA's is the enforcer; the provider's is an additive policy veto.)

---

## 2. The production decision function (final authorization rule)

Let `RA` be the Risk Authority result, `DA` the Decision Authority governance
result, `AG` the ActionGate policy result. The composition engine's disposition
is **fail-closed** and defined as:

```
GRANT (execution-eligible)  if and only if  ALL of:

  1. RA.envelope verifies      (Ed25519 signature, key_id, canonical bytes)   [RA]
  2. RA == ALLOW               (control-derived; grants_authority is true)     [RA]
  3. RA.not_before ≤ now < RA.expires_at                                       [RA]
  4. RA.decision not expired at issuance (F-B)                                 [RA]
  5. RA.envelope not revoked   (RevocationState)                              [RA]
  6. RA.authority_epoch current                                               [RA]
  7. exact action matches signed envelope scope
        (tenant, actor, model, purpose, tools±, data±, destination, amount)    [RA]
  8. DA does NOT veto          (outcome ∉ {HOLD, REJECT, DEFER}; ADVANCE ok)   [DA]
  9. AG does NOT veto          (outcome ∉ {DENY, UNKNOWN})                      [AG]
 10. all governance restrictions applied leave a non-empty effective scope     [∩]

Otherwise → NOT-GRANT (DENY or non-executable HOLD/ERROR; never ALLOW).
```

The **only** authority that authorizes execution is RA's verified, in-scope,
unexpired, unrevoked signed envelope (steps 1–7). DA and AG (steps 8–9) can turn
a GRANT into a NOT-GRANT; they can **never** turn a NOT-GRANT into a GRANT.

### 2.1 Formal authority-strength property

```
FinalAuthority ≤ RiskAuthority          (authority-strength ordering)
FinalScope    ⊆ RiskAuthorityScope      (per-dimension containment)
```

**No governance input — upstream or downstream, permissive or advisory — may
upgrade a Risk Authority DENY, widen scope, or manufacture authority RA did not
issue.** No additive integration may widen `actions`, `resources`, `amount`,
`tenant`, `actor`, `model`, `jurisdiction`, `autonomy`, or `time`.

This is the invariant every later phase (composition algebra §12, tests §15,
F-A/F-B/F-E §8) exists to protect.

---

## 3. Veto precedence — truth table

Vocabulary is drawn from the actual contracts:
`RA ∈ {ALLOW, DENY, ESCALATE}` (RA also has `ALLOW_WITH_CONDITIONS`, treated as
ALLOW + tightening conditions); `DA ∈ {ADVANCE, HOLD, REJECT, DEFER}`;
`AG ∈ {ALLOW, ALLOW_WITH_CONSTRAINTS, DENY, UNKNOWN}`. Additional authority-
critical states: `ERROR` (infra failure), `UNAVAILABLE` (kernel down),
`INVALID_ARTIFACT` (malformed / signature-fail / stale). These are **distinct
from policy DENY** and never mean ALLOW.

Final dispositions are drawn from the RA/platform vocabulary:
- **DENY** — authoritatively denied (policy or authority failure); terminal.
- **HOLD_NON_EXECUTABLE** — governance requires a hold/approval/deferral;
  execution blocked, potentially resumable after governance resolves.
- **ERROR_NON_EXECUTABLE** — authority-critical component failed closed;
  execution blocked; retry/repair path, never an authorization.

`GRANT` = execution-eligible; it still passes through exact-action enforcement
(§1.4) before anything runs.

| # | RA | DA | AG | Envelope/validity | Final disposition | Rationale |
|---|----|----|----|-------------------|-------------------|-----------|
| 1 | DENY | any | any | any | **DENY** | RA DENY is absorbing; nothing upgrades it. |
| 2 | ESCALATE | any | any | any | **HOLD_NON_EXECUTABLE** | RA itself withheld a grant; no downstream ALLOW. |
| 3 | ALLOW | REJECT | any | valid | **DENY** | Organizational veto (terminal). |
| 4 | ALLOW | HOLD | any | valid | **HOLD_NON_EXECUTABLE** | Governance hold; not executable. |
| 5 | ALLOW | DEFER | any | valid | **HOLD_NON_EXECUTABLE** | Deferred decision; not executable. |
| 6 | ALLOW | ADVANCE | DENY | valid | **DENY** | Action-type policy veto. |
| 7 | ALLOW | ADVANCE | UNKNOWN | valid | **DENY** | `UNKNOWN` never authorizes (fail-closed). |
| 8 | ALLOW | ADVANCE | ALLOW | valid | **GRANT → exact-action** | Only all-clear path; still enforced at §1.4. |
| 9 | ALLOW | ADVANCE | ALLOW_WITH_CONSTRAINTS | valid | **GRANT → exact-action, tightened** | Constraints intersected into effective scope (§12). |
| 10 | ALLOW | ADVANCE | ALLOW | **invalid artifact** (sig fail / tamper / stale) | **DENY** | Envelope verification is RA-owned and mandatory. |
| 11 | ALLOW | ADVANCE | ALLOW | **expired/revoked/stale epoch** | **DENY** | RA validity checks fail closed. |
| 12 | ALLOW | *DA ERROR/UNAVAILABLE* | any | valid | **ERROR_NON_EXECUTABLE** (see §4 policy) | Authority-critical governance input missing → fail closed. |
| 13 | ALLOW | ADVANCE | *AG ERROR/UNAVAILABLE* | valid | **ERROR_NON_EXECUTABLE** (see §4 policy) | Additive gate could not run → fail closed. |
| 14 | *RA ERROR/UNAVAILABLE* | any | any | any | **ERROR_NON_EXECUTABLE** | No RA authority basis → never execute. |
| 15 | ALLOW | ADVANCE | ALLOW | valid but **empty effective scope** (∩ = ∅) | **DENY** | Restriction algebra emptied the grant. |

**Precedence summary (highest-priority wins, all fail-closed):**
`RA DENY / invalid / expired / revoked` **>** `DA REJECT` **>** `AG DENY/UNKNOWN`
**>** `DA HOLD/DEFER` **>** `ERROR/UNAVAILABLE (fail-closed)` **>** `GRANT`.
Execution never proceeds on ambiguous state.

> Whether `HOLD` and `DEFER` are surfaced distinctly (resumable vs re-queued)
> from `DENY` is a **presentation / workflow** choice in the output contract
> (§14); it does **not** affect executability — all three block execution.

---

## 4. Failure semantics (fail-closed)

**Invariant: `failure ≠ ALLOW`.** Every failure classifies to a non-executable
disposition. Classification uses the platform vocabulary from §3.

| Failure | Classification | Notes |
|---|---|---|
| Decision Authority unavailable | **ERROR_NON_EXECUTABLE** | If DA is a *required* governance input for the tenant/policy, its absence blocks. (A deployment MAY configure DA as optional; that is an explicit, recorded policy, and even then DA can only *veto*, never grant.) |
| ActionGate provider unavailable | **ERROR_NON_EXECUTABLE** | Additive gate could not run; do not silently skip it. |
| Risk Authority unavailable | **ERROR_NON_EXECUTABLE** | No machine-authority basis exists → never execute. |
| Revocation store unavailable | **ERROR_NON_EXECUTABLE** | Cannot prove not-revoked → treat as unauthorized. |
| Trusted clock unavailable | **ERROR_NON_EXECUTABLE** | Cannot evaluate validity window (relates to F-G/#1398). |
| Signature verification failure | **DENY** | Authoritative: the artifact is not genuine. |
| Malformed kernel response | **ERROR_NON_EXECUTABLE** | Integrity failure; never coerce to ALLOW (kernels already refuse this — `mapping/result.py`, response-integrity gate). |
| Unknown decision outcome | **DENY** | `UNKNOWN`/`INDETERMINATE` never authorize. |
| Stale policy version | **ERROR_NON_EXECUTABLE** | Cannot rely on outdated policy; fail closed pending refresh. |

Rationale for the DENY vs ERROR split: **DENY** is an authoritative negative
about *this* request (safe to treat as final); **ERROR_NON_EXECUTABLE** signals a
missing/failed authority input where the correct action is to *not execute* and
surface a repair/retry path — never to proceed. Both are `≠ ALLOW`.

---

## 5. Corrected trust-boundary diagram

```
Workflow / Agent / System
        │
        ▼
Risk evaluation / controls  (RiskEngine over persisted ControlResults)   [RA owns]
        │
        ▼
Risk Authority  ── control-derived machine authority, scope, monotonicity [RA owns]
        │
        ▼
signed RiskAuthorizationEnvelope  (Ed25519, scope, nbf/exp, epoch)       [RA issues]
        │
════════════════════════════════════════════════════════════════════════
                     MACHINE AUTHORITY BOUNDARY
   (nothing below may create or widen authority — only subtract it)
════════════════════════════════════════════════════════════════════════
        │
        ▼
Governance Composition Engine   (integration package)                    [composes]
        │
        ├──▶ Decision Authority governance input   (ADVANCE/HOLD/REJECT/DEFER veto)  [DA vetoes]
        │
        ├──▶ ActionGate policy input               (action_type ALLOW/DENY veto)     [AG vetoes]
        │
        ▼
RA envelope verification        (reuse EnvelopeVerifier)                  [RA verifies]
        │
        ▼
Exact-action match              (CanonicalAction.digest vs envelope scope)[RA verifies]
        │
        ▼
Effective-scope intersection    (RA ∩ governance restrictions)           [engine, ⊆ RA]
        │
        ▼
execution eligible   (only if every check above passed)
```

Ownership legend — who does what:

| Function | Owner |
|---|---|
| Issue machine authority (scope + envelope) | **Risk Authority** |
| Verify envelope signature / time / revocation / epoch | **Risk Authority** (via integration reuse) |
| Verify exact-action scope match | **Risk Authority** (via integration reuse) |
| Contribute organizational veto (human/committee/SoD) | **Decision Authority** |
| Contribute action-type policy veto | **ActionGate provider** |
| Compose the above fail-closed; apply restrictions | **Integration package** (composition engine) |
| Execute | downstream executor (out of RA-4.5 scope) |

---

## 6. Corrected RA-4.5 component model

The original substitution adapters (`KernelDecisionAuthorityAdapter`,
`KernelActionGateAdapter` *as replacements*) are replaced by **additive
composition** concepts. Names are **proposals**, reconciled with monorepo
conventions at implementation kickoff (not finalized here):

| Concept (proposed) | Responsibility |
|---|---|
| `DecisionAuthorityGovernanceAdapter` | Translate `ugence-decision-authority` outcomes into a `GovernanceVetoResult` (ADVANCE=no-veto; HOLD/DEFER=hold; REJECT=deny). Never produces an RA `Scope` or ALLOW. |
| `ActionGatePolicyAdapter` | Translate `ugence-actiongate-provider` outcomes into a `GovernanceVetoResult` + tightening constraints. `DENY`/`UNKNOWN`=veto; `ALLOW_WITH_CONSTRAINTS`=tightening obligations. Never verifies-away RA checks. |
| `GovernanceVetoResult` | Value object: `{disposition ∈ {NO_VETO, HOLD, DENY, ERROR}, restrictions, reason_codes, source_version}`. Deliberately has **no ALLOW/scope-minting capability**. |
| `RiskAuthorityCompositionEngine` | Orchestrates: RA authority + envelope verify + exact-action match, then folds in each `GovernanceVetoResult` fail-closed, applies restriction algebra (§12), emits the output contract (§14). |

The adapters translate kernel outputs into **additional restrictions, vetoes,
holds, or non-executable governance state** — *never* into manufactured RA ALLOW
authority.

---

## 7. Dependency architecture

Preserve `risk_authority` as a **stdlib-only leaf**. Production composition lives
**outside** the leaf.

```
        risk_authority           (stdlib-only leaf; defines the ports)
              ▲
              │  (integration imports RA's public API; RA imports nothing below)
              │
   risk-authority-runtime /      (integration / governance-composition package)
   governance-composition pkg    (owns the composition engine + adapters)
              │
              ├── ugence-decision-authority
              └── ugence-actiongate-provider
```

Constraints (verified feasible by the audit, Phase 13):

- **No dependency cycle.** DA and AG do not import each other or RA; the
  integration package imports all three one-way.
- **Risk Authority does not import the kernels** — the single-wheel,
  `--no-index`, zero-dependency install proof continues to hold.
- **Canonical kernels do not import Risk Authority** (no reverse dependency
  unless separately justified and reviewed).
- **The integration package owns composition** — wiring production kernels is a
  deliberate, visible act, never an implicit import side effect.

**Tentative location (not finalized):** `packages/integration/risk-authority-runtime/`
(import `ugence_risk_authority_runtime`), reconciled with the monorepo
`packages/…` convention at kickoff.

The leaf-safe DI seam is unchanged from the original plan and remains the first
code change of RA-4.5 (it adds **no** dependency to the leaf):

```
RiskAuthorityApplication(
    decision_authority=...,   # DecisionAuthorityPort  (reference default; production adapter injected)
    action_gate=...,          # ActionGatePort         (reference default; production adapter injected)
)
```

---

## 8. F-A / F-B / F-E preservation (proved by design)

**F-A — a failed mandatory control cannot become ALLOW.** The binding RA
`RiskOutcome` is derived by RA's own `RiskEngine` over persisted `ControlResult`s
(the `api/dependencies.py:307-315` seam) **before** any kernel is consulted, and
that seam stays in RA. Governance inputs enter only as vetoes (§3). Therefore a
`DA ADVANCE`, an `AG ALLOW`, an adapter default, or a caller-supplied
recommendation **cannot** manufacture ALLOW: the composition engine reads RA's
already-derived outcome and only ever *subtracts*. The audit's standing warning
— the DA kernel offers *no* F-A protection for the machine-authority case because
its binding outcome is caller-asserted — is honored by making the adapter/engine
the fail-closed boundary that never lets a kernel disposition become the RA
outcome.

**F-B — an expired `RiskDecision` cannot mint or refresh authority.** Expiry is
enforced at RA's `EnvelopeIssuer` (`services/envelope_issuer.py:81-86`), which is
RA-owned and stays the mint boundary. Neither DA nor AG can represent, extend, or
refresh RA expiry (DA has no decision expiry; AG's `authorization_expired` bool is
unread). The composition engine never re-stamps validity — it can only reject on
`now ≥ expires_at`, never extend it.

**F-E — duplicate controls cannot mask failure.** Control results are grouped per
control ID in RA (`FAIL` can never be hidden by a later `PASS`), and the RA
`RiskEngine` remains the sole control-derivation authority. No downstream kernel
result is a control result, so none can compensate for an unsatisfied required
control. Composition adds gates; it never adds control evidence.

All three regressions must run **against the production-composition path**, not
only the reference path (§15).

---

## 9. F-D treatment (#1397 — remains separate)

Confirmed against current code: `CanonicalAction` has **no `jurisdiction` and no
`autonomy` field**, and the production ActionGate provider treats `resource` /
`jurisdiction` as opaque/emit-only and has **no autonomy representation**.
Therefore F-D (resource/target, jurisdiction, autonomy enforcement) **cannot** be
closed by composing onto the production kernels.

**F-D stays a separate work item (#1397):** it requires extending
`CanonicalAction` and `ReferenceActionGate`, under separate review. It is **not** a
dependency of this composition architecture and must not be folded into it.

> **Explicit non-claim.** RA-4.5 composition MUST NOT claim jurisdiction,
> autonomy, or resource/target are *enforced* merely because `Scope` carries
> those fields. `Scope.jurisdictions` and `Scope.max_autonomy_level` bound
> **issuance-time monotonicity** only; they are not matched against a presented
> action until #1397 lands. No unsupported field is silently mapped through a
> kernel. Until #1397, the three F-D rows in the differential suite (§15) are
> **documented divergences**, not parity failures.

---

## 10. Human governance vs machine authority (explicit)

Two different things that must never be conflated:

- **Organizational approval** (Decision Authority): *"the organization does not
  object."* A committee `ADVANCE` is an absence of organizational veto.
- **Machine execution authority** (Risk Authority): *"this exact machine
  capability is authorized, signed, scoped, and time-bound."*

Therefore:

- `ADVANCE` means **only** "governance does not veto." It does **not** imply the
  machine may execute anything — RA's envelope + scope still determine the actual
  machine capability, and execution is bounded by RA, never by DA's approval.
- `HOLD` / `REJECT` / `DEFER` **prevent execution** even when RA would otherwise
  permit it, wherever the composition policy treats DA as a required governance
  input (§3 rows 3–5; §4). Governance can subtract; it cannot add.

An organization saying "yes" is necessary-but-not-sufficient; RA saying "yes"
(verified, in-scope, unexpired) is what authorizes the machine.

---

## 11. ActionGate policy semantics — how AG outputs interact with RA

The provider can emit typed policy values (`maximum_amount`, `allowed_region`,
`required_approval`). These are treated as **restrictions to intersect into** the
effective scope — **only** where the semantics are compatible and only in the
*tightening* direction:

- **Never union permissions.** An AG output can only make the effective grant
  narrower or add an obligation, never wider.
- **Amount (compatible → intersect via `min`):**
  - `RA = max $5,000`, `AG = max $3,000` → **final ≤ $3,000** (AG tighter wins).
  - `RA = max $5,000`, `AG = max $10,000` → **final = $5,000** (RA cap holds; AG
    cannot raise it).
- **`required_approval`:** additive obligation → strengthens the approval
  requirement (union of required approvals / strongest requirement), never
  weakens it.
- **`allowed_region` / jurisdiction:** because F-D is unresolved and RA does not
  yet *enforce* jurisdiction at the gate, an AG `allowed_region` is recorded as a
  governance obligation but is **not** treated as satisfying/enforcing RA
  jurisdiction (no silent mapping, §9). It may only *further deny*, never permit.

Formal rule (monotone restriction): for every dimension `d` that both sides
represent compatibly, `Final(d) = tighten(RA(d), AG(d))` with
`Final(d) ⊑ RA(d)`. For dimensions AG does not compatibly represent,
`Final(d) = RA(d)` (unchanged) — AG is simply silent there.

---

## 12. Composition algebra

General restriction operator:

```
EffectiveAuthority = RA_Authority ∩ GovernanceRestrictions
with  EffectiveAuthority ⊆ RA_Authority   (always; equality when no restriction applies)
```

Per-dimension safe operators (applied **only** to dimensions the contributing
kernel actually represents compatibly):

| Dimension | Operator | Direction |
|---|---|---|
| amount ceiling | `min()` | ↓ tighten |
| autonomy level | `min()` | ↓ tighten |
| expiry / validity | `earliest()` | ↓ shorten |
| allow-set (tools, data, purposes, destinations) | `intersection` | ↓ shrink |
| deny-set (tools, data) | `union` | ↑ grow the *denial* (= tighten authority) |
| jurisdiction | `intersection` | ↓ shrink |
| required approvals | `union` / strongest-requirement | ↑ strengthen obligation |
| disposition | fail-closed veto (§3) | any veto → not-grant |

**Safe-to-compose (production kernels represent it):** disposition/veto (DA + AG),
`action_type` policy (AG), required approvals / SoD (DA), and AG's emitted
*tightening* obligations where compatible.

**NOT safe to compose through the kernels (do not apply operators here):**
authority `Scope` subset, amount/tools/data/destination *matching*, signature,
revocation, epoch, jurisdiction/autonomy *enforcement* — these are **RA-owned**
and remain computed by RA's own logic, never derived from a kernel. Applying a
composition operator to a dimension a kernel does not represent would be a silent
default, which the audit forbids.

Result: composition can only **preserve or reduce** authority; there is no
operator, on any dimension, that enlarges it.

---

## 13. Signature / artifact ownership

Per the audit (corroborated): RA has signed Ed25519 envelopes; DA uses unsigned
canonical/content hashes (`canonical_hash`, CER `content_hash` = plain sha256);
ActionGate produces only an sha256 fingerprint of its own *output* and verifies
no RA signature.

Therefore:

- The **`RiskAuthorizationEnvelope` remains the authoritative machine-execution
  artifact.** It is **not** translated into an unsigned kernel artifact that is
  then treated as equivalent authority.
- Verification order is fixed:

```
signed RA envelope
     ↓  verified (RA EnvelopeVerifier: signature, key_id, nbf/exp, revocation, epoch)
governance restrictions applied  (DA + AG vetoes/obligations, fail-closed, tightening only)
     ↓
exact-action match  (CanonicalAction.digest vs verified envelope scope)
     ↓
execution eligible
```

- If an adapter must build a kernel request (e.g. to ask DA/AG their governance
  question), that request is a **governance-query artifact**, not a replacement
  for the signed capability. The RA envelope and the production CER **cannot be
  translated into one another without re-authorizing** (different fields; signed
  vs unsigned trust models) — so no such translation is performed.

---

## 14. Composition output contract (design only — not implemented)

A single governed decision object, preserving (not re-minting) the RA envelope:

```
GovernedExecutionDecision {
    risk_authority_result       # RA disposition + verified envelope reference (authoritative)
    decision_authority_result   # DA outcome + reason codes (governance evidence)
    actiongate_result           # AG outcome + emitted constraints/obligations
    effective_constraints       # RA_scope ∩ governance restrictions (⊆ RA scope)
    final_disposition           # GRANT / DENY / HOLD_NON_EXECUTABLE / ERROR_NON_EXECUTABLE
    reason_codes                # structured, per-source (no cross-vocabulary equality asserted)
    non_executable_reason       # populated when final_disposition ≠ GRANT
    source_versions             # DA/AG/RA + policy versions (for stale-policy detection)
    correlation_id              # request correlation
}
```

**Do not mint a second independent authorization envelope.** The signed
`RiskAuthorizationEnvelope` remains *the* machine-execution authority; the
`GovernedExecutionDecision` wraps it with governance evidence and the computed
effective constraints, and demonstrates **why** execution is eligible or blocked.
Any signed re-issuance would create a competing authority artifact — explicitly
disallowed.

---

## 15. Differential / composition test plan (design only)

Run identical scenarios through the **reference stack**
(`ReferenceDecisionAuthority` + `ReferenceActionGate`) and the
**production-composition stack** (`DecisionAuthorityGovernanceAdapter` +
`ActionGatePolicyAdapter` + `RiskAuthorityCompositionEngine`). Assertion level
(per audit Phase 11): **disposition + fact-of-scope-reduction + binding
identity** — do **not** assert reason-code/error-string equality (vocabularies
are unrelated). Where production is deliberately stricter, assert
`reference=ALLOW ⇒ production ∈ {ALLOW, DENY/HOLD}`, never the reverse.

**Core veto matrix (must hold):**

| Scenario | Expected final |
|---|---|
| RA DENY + DA ADVANCE + AG ALLOW | **DENY** |
| RA ALLOW + DA REJECT + AG ALLOW | **DENY** |
| RA ALLOW + DA HOLD + AG ALLOW | **HOLD_NON_EXECUTABLE** |
| RA ALLOW + DA DEFER + AG ALLOW | **HOLD_NON_EXECUTABLE** |
| RA ALLOW + DA ADVANCE + AG DENY | **DENY** |
| RA ALLOW + DA ADVANCE + AG UNKNOWN | **DENY** |
| RA ALLOW + DA ADVANCE + AG ALLOW | **GRANT → exact-action** |

**Restriction algebra:**

| Scenario | Expected |
|---|---|
| AG amount stricter than RA ($3k vs $5k) | effective ≤ $3,000 |
| AG amount broader than RA ($10k vs $5k) | effective = $5,000 (RA cap holds) |

**Envelope / identity enforcement (all adapter/RA-enforced — the kernels alone
would ALLOW/ignore these, which is the point):**

| Scenario | Expected |
|---|---|
| RA envelope expired | DENY |
| RA envelope revoked | DENY |
| RA signature invalid / tampered payload | DENY |
| stale authority epoch | DENY |
| wrong tenant / wrong actor / wrong model | DENY |
| payload substitution | DENY |
| wrong workflow / policy digest | DENY |
| failed mandatory control (F-A) | DENY |
| duplicate FAIL+PASS control (F-E) | DENY |
| expired decision at issuance (F-B) | DENY |

**Availability / failure (fail-closed, §4):**

| Scenario | Expected |
|---|---|
| DA unavailable | ERROR_NON_EXECUTABLE |
| AG unavailable | ERROR_NON_EXECUTABLE |
| RA unavailable | ERROR_NON_EXECUTABLE |
| malformed kernel response | ERROR_NON_EXECUTABLE |

**F-D rows (documented divergence until #1397):** wrong target/resource, wrong
jurisdiction, autonomy-too-high → reference ALLOWs at the gate today; production
DENYs only after #1397. Marked divergence, not failure.

The suite proves the corrected property: **composition can only preserve or
reduce authority, never enlarge it** — every production DENY above is
RA/adapter-enforced, demonstrating the kernels are additive gates, not the
enforcers.

---

## 16. Non-goals (unchanged)

RA-4.5 remains narrowly a **governance-composition** integration. It is **not** a
vehicle for RA-5+, TAP expansion, Control Assurance, Trajectory Control, ACP,
reconciliation, cloud scaling, GRC dashboards, Agent Runtime redesign, Decision
Authority redesign, ActionGate redesign, or general policy-engine redesign.

---

## 17. Implementation-readiness criteria (gate before any code)

Adapter/composition code MAY begin **only** after all of:

1. this corrected architecture is **approved**;
2. the veto truth table (§3) is finalized;
3. the failure semantics (§4) are finalized;
4. the composition algebra (§12) is finalized;
5. the integration package location (§7) is agreed;
6. F-A / F-B / F-E preservation (§8) is accepted **by design**;
7. F-D (#1397) is confirmed **out of scope** for RA-4.5;
8. the signed RA envelope is confirmed to remain **the** machine-execution
   authority (§13);
9. it is confirmed that **no authority-widening path exists** in the design.

The leaf-safe DI seam (§7) is the expected first code change; adapters follow only
after this gate.

---

## 18. Verdict

# ARCHITECTURE_CORRECTED_READY_FOR_APPROVAL

The corrected model is internally consistent and preserves every RA authority
guarantee: Risk Authority remains the sole machine-authority-scope issuer and
signed-envelope enforcer; Decision Authority and ActionGate are additive,
fail-closed governance vetoes that can only preserve or reduce authority;
`FinalAuthority ≤ RiskAuthority` and `FinalScope ⊆ RiskAuthorityScope` hold by
construction; F-A/F-B/F-E are preserved and F-D remains a separate, non-blocking
work item. No production code is changed and no adapters are implemented by this
document.
