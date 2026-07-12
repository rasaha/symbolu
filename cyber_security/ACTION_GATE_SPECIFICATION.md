# Action Gate Specification — Deterministic Interface Contract

**Status:** the canonical, implementation-facing contract for the pre-commit admissibility gate.
Every gateway implementation MUST conform to this document. It is the machine-level realization
of `AGENT_ACTION_ADMISSIBILITY_MVP.md` (the product spec) and `ROADMAP.md` §0–§3 (the beachhead
of record). Documentation only — no production code; no pseudocode beyond interface contracts.

Conformance keywords **MUST / MUST NOT / SHOULD / MAY** are used in the RFC-2119 sense.

---

## 1. Purpose

This specification defines the **deterministic interface contract** for the pre-commit
admissibility gate: the fixed inputs, the policy-evaluation semantics, the decision state
machine, the six decision outcomes, the simulation and approval contracts, and the immutable
audit record.

The **core of the gate is deterministic**: given the same canonical action envelope, the same
signed policy version, and the same evidence set, the gate MUST produce the same decision. All
other components — simulators, blast-radius/consequence engines, MCP and non-MCP adapters, AI
advisors, credential brokers, behavioral evidence (BCVF/USE/SCC), and UI — **plug into this
contract as evidence producers or transport**. They MAY add evidence; they **MUST NOT** alter
the deterministic policy evaluation or approve an action (§3, §12).

Everything downstream in the build (`ROADMAP.md` §3, MVP §12 Stages) is an implementation of
this contract. This document does not change the MVP's technical content; it makes it executable.

---

## 2. Canonical Action Envelope

The gate operates only on this framework-neutral object. Adapters (§12) translate any
vendor-specific call into it. Each field appears **exactly once** in the canonical enumeration
below.

Types: `string`, `enum{…}`, `hash` (hex digest of a named canonicalization), `timestamp`
(RFC-3339 UTC), `object`, `array<T>`, `duration`.

| # | Field | Type | R/O | Description | Validation rules |
|---|---|---|---|---|---|
| 1 | `action_id` | `string` (UUID) | R | Unique id for this attempted transition. | non-empty; UUIDv4; unique per episode |
| 2 | `timestamp` | `timestamp` | R | Envelope creation time. | valid RFC-3339 UTC; within clock-skew bound of gate |
| 3 | `agent_identity` | `object{id, key_id, sig}` | R | Cryptographic identity of the acting agent. | signature verifies against a registered agent key |
| 4 | `runtime` | `string` | R | Agent runtime/framework (MCP host, SDK, custom). | non-empty; from the registered runtime set |
| 5 | `model_provider` | `object{model, provider}` | R | Model + provider producing the decision. | both non-empty |
| 6 | `delegator` | `object{id, type:enum{HUMAN,SERVICE}}` | R | Principal on whose authority the agent acts. | resolvable principal |
| 7 | `delegation_chain` | `array<object{from,to,grant,exp}>` | R | Ordered chain of delegations. | contiguous; each link unexpired; roots at `delegator` |
| 8 | `objective` | `string` | R | The task/purpose the agent was given. | non-empty (semantic use is Tier-3 advisory only) |
| 9 | `tool` | `object{server_id, tool_name}` | R | Tool/server the operation targets. | registered tool surface |
| 10 | `operation` | `enum{TRANSITION_CLASS}` | R | Typed operation; maps to a transition class (§10). | in the registered operation taxonomy |
| 11 | `target_resource` | `array<string>` | R | Resource identifier(s) affected. | non-empty; well-formed resource URNs |
| 12 | `arguments` | `object` | R | Normalized operation arguments. | schema-valid for the `operation` |
| 13 | `credential_scope` | `object{principal, permissions[], ttl}` | R | Credential + effective privilege being exercised. | permissions ⊆ delegated authority (privilege monotonicity) |
| 14 | `current_state_hash` | `hash` | R | Digest of the relevant current observed state snapshot. | hex; matches gate-recomputed hash within freshness window |
| 15 | `state_freshness` | `object{as_of:timestamp, source}` | R | Age/source of the state snapshot. | `as_of` within per-class freshness bound |
| 16 | `linked_ticket` | `string` | O | Ticket / change-request reference. | if present: resolvable; not self-authored where SoD applies |
| 17 | `approvals` | `array<Approval>` | O | Approvals already collected (§8). | each Approval valid per §8 |
| 18 | `attestation` | `object{type, evidence, exp}` | O | Device/runtime attestation. | if present: verifies; unexpired |
| 19 | `policy_version` | `string` (semver+hash) | R | Signed policy version to evaluate against (§4, §13). | matches a signed, active policy in the root-of-trust |
| 20 | `rollback_plan` | `object{steps[], verified:bool}` | O | Declared rollback. | if present: well-formed; `verified` set only by a rollback checker |
| 21 | `reversibility` | `enum{REVERSIBLE, REVERSIBLE_WITH_COST, IRREVERSIBLE}` | R | Declared reversibility class. | in enum; gate MAY override upward on evidence |
| 22 | `expected_effects` | `array<Effect>` | O | Simulator-produced predicted effects (§7). | each carries a `simulation_version` + fidelity |
| 23 | `correlation_id` | `string` | R | Session/actor correlation id (sequence grouping). | non-empty |
| 24 | `sequence_id` | `string` | R | Monotonic id within a correlation for structuring detection. | non-empty; monotonic within `correlation_id` |

**Field discipline.** Any missing/malformed **required** field ⇒ `DENY` at `VALIDATED` (fail-to-
safe). **Optional** fields may only *raise* achievable assurance; their absence MUST NOT lower a
hard requirement.

**MVP crosswalk (consistency).** These names are the canonical machine schema; each maps 1:1 to
an `AGENT_ACTION_ADMISSIBILITY_MVP.md` §2 concept: `runtime`←`agent_runtime`,
`objective`←`delegated_objective`, `tool`←`tool_server_identity`,
`credential_scope`←`credential_privilege_scope`, `current_state_hash`←hash(`current_observed_state`),
`expected_effects`←`predicted_effects`, `reversibility`←`reversibility_class`,
`linked_ticket`←`linked_change`, `attestation`←`attestation_evidence`,
`correlation_id`+`sequence_id`←`correlation_ids`. `timestamp` is added for audit/replay binding.
No concept is dropped or broadened.

**Complete JSON example (T1 — grant IAM admin):**
```json
{
  "action_id": "8b2f2c9e-1a44-4c0e-9b1a-2f6c9d0e5a71",
  "timestamp": "2026-07-12T14:03:11Z",
  "agent_identity": {"id": "agent://sre-bot/az-1", "key_id": "k7", "sig": "base64…"},
  "runtime": "mcp-host/1.2",
  "model_provider": {"model": "claude-opus-4-8", "provider": "anthropic"},
  "delegator": {"id": "user://alice", "type": "HUMAN"},
  "delegation_chain": [
    {"from": "user://alice", "to": "agent://sre-bot/az-1", "grant": "iam:manage", "exp": "2026-07-12T18:00:00Z"}
  ],
  "objective": "Onboard new service account for billing pipeline",
  "tool": {"server_id": "cloud-iam", "tool_name": "attach_role_policy"},
  "operation": "IAM_GRANT_ADMIN",
  "target_resource": ["arn:aws:iam::acct:role/billing-sa"],
  "arguments": {"policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"},
  "credential_scope": {"principal": "agent://sre-bot/az-1", "permissions": ["iam:AttachRolePolicy"], "ttl": "PT10M"},
  "current_state_hash": "sha256:3f9a…",
  "state_freshness": {"as_of": "2026-07-12T14:03:05Z", "source": "iam-live"},
  "linked_ticket": "CHG-10432",
  "approvals": [],
  "attestation": {"type": "workload-identity", "evidence": "base64…", "exp": "2026-07-12T14:10:00Z"},
  "policy_version": "1.4.0+sha256:aa11…",
  "rollback_plan": {"steps": ["detach_role_policy AdministratorAccess"], "verified": false},
  "reversibility": "REVERSIBLE_WITH_COST",
  "expected_effects": [],
  "correlation_id": "sess-77c1",
  "sequence_id": "sess-77c1:0007"
}
```

---

## 3. Deterministic Gate Inputs

All evidence entering the gate, by class. **Hard classes are dispositive; advisory classes are
never dispositive and MUST NOT override a hard constraint.**

| Class | Source | Authority | Notes |
|---|---|---|---|
| **Policy** | signed policy `policy_version` (§4, root-of-trust) | **HARD** | the deterministic ruleset; the only source that can *auto-admit* |
| **Attestation** | `attestation` field / attestation verifier | **HARD (gating)** | presence/validity gates classes that `REQUIRE_ATTESTATION` |
| **Credential scope** | `credential_scope` + broker | **HARD** | privilege monotonicity; permissions ⊆ delegated authority |
| **Current state** | `current_state_hash` + `state_freshness` | **HARD (gating)** | stale beyond class bound ⇒ cannot auto-admit |
| **Hard evidence** | verified backups, rollback verification, dependency facts | **HARD** | required by specific invariants (e.g. `MUST_HAVE backup`) |
| **Simulation evidence** | simulator reports (§7) | **CONDITIONAL** | authoritative only within stated coverage at ≥ required fidelity |
| **Human approvals** | `approvals` (§8) | **HARD (resolving)** | resolve `REQUIRE_APPROVER`; bound to action+policy hash |
| **Advisory AI evidence** | Tier-3 semantic analysis (§ MVP 5) | **ADVISORY** | may only *escalate* / annotate; never admit, never lower assurance |
| **Behavioral evidence (optional)** | BCVF / USE / SCC / anomaly | **ADVISORY, OPTIONAL** | off critical path; may only add escalation signal; gate works without it |

**Invariant (non-compensatory composition):** hard classes are evaluated first and are
dispositive. Advisory and optional classes are consulted **only within the region the hard
classes leave open**, and may only move a decision toward **more** assurance (escalate), never
toward **less**. No advisory score, model confidence, or behavioral signal can satisfy a
`MUST_HAVE`, clear a `FORBID`, or approve an action.

---

## 4. Hard Invariant Language

A small, deterministic, human-ratified, signed policy language over
`(envelope, current_state, expected_effects)`. Grammar (interface contract, not code):

```
rule    := WHEN <match> THEN <effect>+
match   := operation == <OP> [ AND <condition> ]*
effect  := ALLOW
         | DENY
         | REQUIRE <predicate>              # hard condition; unmet → DENY
         | MUST_HAVE <evidence>             # named evidence present+valid; unmet → REQUEST_MORE_EVIDENCE
         | FORBID <predicate>               # if predicate true → DENY
         | MAX_SCOPE <n>                     # affected-count ≤ n; exceeded → ESCALATE_TO_HUMAN
         | MAX_COST <amount>                # projected cost ≤ amount; exceeded → ESCALATE_TO_HUMAN
         | MAX_BLAST_RADIUS <n>             # reachable-resource count ≤ n; exceeded → ESCALATE_TO_HUMAN
         | MAX_IRREVERSIBILITY <class>      # reversibility ≤ class; worse → ESCALATE_TO_HUMAN (+robust viability)
         | REQUIRE_APPROVER <policy>        # valid approval per policy; unmet → ESCALATE_TO_HUMAN
         | REQUIRE_SIMULATION <fidelity>    # sim report ≥ fidelity present; unmet → SIMULATE_AND_RETRY
         | REQUIRE_ATTESTATION <type>       # attestation of type valid; unmet → REQUEST_MORE_EVIDENCE
```

**Determinism rules.** Effects compose by a fixed precedence: `DENY`/`FORBID`-hit ≻
`REQUIRE`-unmet ≻ `MUST_HAVE`/`REQUIRE_ATTESTATION`-unmet ≻ `REQUIRE_SIMULATION`-unmet ≻
`REQUIRE_APPROVER`/`MAX_*`-exceeded ≻ `ALLOW`. The **most restrictive** triggered effect wins;
ties resolve to the earlier item in this precedence list. Rule order MUST NOT affect the result.

**Ten example invariant rules:**

1. `WHEN operation == IAM_GRANT_ADMIN AND grantee == credential_scope.principal THEN DENY`  (no self-privilege-broadening)
2. `WHEN operation == IAM_GRANT_ADMIN THEN REQUIRE_APPROVER dual_control AND REQUIRE_ATTESTATION workload-identity`
3. `WHEN operation == DB_DELETE THEN MUST_HAVE verified_restorable_backup AND FORBID last_replica AND MAX_IRREVERSIBILITY REVERSIBLE_WITH_COST`
4. `WHEN operation == NET_EXPOSE AND target.tag == sensitive THEN DENY`
5. `WHEN operation == NET_EXPOSE AND cidr == "0.0.0.0/0" AND port in ADMIN_PORTS THEN DENY`
6. `WHEN operation == SECRET_READ THEN FORBID export_to_unapproved_sink AND FORBID bulk_enumeration AND REQUIRE_APPROVER single`
7. `WHEN operation == MONITORING_DISABLE THEN FORBID target == gate_audit_path AND REQUIRE_APPROVER dual_control`
8. `WHEN operation == DB_MUTATION THEN FORBID unbounded_predicate AND REQUIRE_SIMULATION MEDIUM AND MAX_SCOPE 10000`
9. `WHEN operation == CLOUD_SPEND_INCREASE THEN FORBID self_approved AND MAX_COST budget_class_cap AND REQUIRE_APPROVER budget_owner`
10. `WHEN operation == EXTERNAL_COMMS AND content.type == free_text THEN DENY; WHEN operation == EXTERNAL_COMMS THEN REQUIRE approved_template AND REQUIRE_APPROVER comms_owner`

Provenance: the ruleset is **signed by an out-of-band root of trust**, versioned (`policy_version`),
reviewed, rollback-able, and **never mutated by AI components** (MVP §4).

---

## 5. Decision State Machine

**States:** `RECEIVED`, `VALIDATED`, `INVARIANT_CHECK`, `SIMULATION_CHECK`, `CONSEQUENCE_CHECK`,
`APPROVAL_CHECK`, `FINAL_DECISION`, `AUDIT_LOGGED`, `COMMITTED`, `DENIED`, `ESCALATED`.

`AUDIT_LOGGED` is mandatory before any terminal state — **no decision leaves the gate
unaudited.** Terminal states: `COMMITTED`, `DENIED`, `ESCALATED`. The retry-class outcomes
(`SIMULATE_AND_RETRY`, `REQUEST_MORE_EVIDENCE`) **rest at `AUDIT_LOGGED`** (returned to caller,
not committed); a resubmission begins a fresh `RECEIVED`.

**Transition table (complete; every state has defined transitions):**

| From | Condition | To |
|---|---|---|
| `RECEIVED` | envelope well-formed, required fields valid | `VALIDATED` |
| `RECEIVED` | malformed / missing required field | `DENIED` (via `AUDIT_LOGGED`) |
| `VALIDATED` | always | `INVARIANT_CHECK` |
| `INVARIANT_CHECK` | hard `DENY`/`FORBID`/`REQUIRE`-fail | `FINAL_DECISION`=DENY |
| `INVARIANT_CHECK` | `REQUIRE_SIMULATION` unmet | `SIMULATION_CHECK` |
| `INVARIANT_CHECK` | passes; no sim required | `CONSEQUENCE_CHECK` |
| `SIMULATION_CHECK` | sim present ≥ required fidelity | `CONSEQUENCE_CHECK` |
| `SIMULATION_CHECK` | sim missing/low-fidelity | `FINAL_DECISION`=SIMULATE_AND_RETRY |
| `CONSEQUENCE_CHECK` | within `Viab̂(A)` (Tier1+trusted Tier2), no approver required | `FINAL_DECISION`=ALLOW / ALLOW_WITH_CONSTRAINTS |
| `CONSEQUENCE_CHECK` | `MAX_*` exceeded / `MAX_IRREVERSIBILITY` / approver required | `APPROVAL_CHECK` |
| `CONSEQUENCE_CHECK` | uncertain (outside kernel, not unsafe) / advisory escalation | `FINAL_DECISION`=ESCALATE_TO_HUMAN |
| `CONSEQUENCE_CHECK` | evidence gap (`MUST_HAVE`/attestation) | `FINAL_DECISION`=REQUEST_MORE_EVIDENCE |
| `APPROVAL_CHECK` | valid binding approval present (§8) | `FINAL_DECISION`=ALLOW / ALLOW_WITH_CONSTRAINTS |
| `APPROVAL_CHECK` | approval absent | `FINAL_DECISION`=ESCALATE_TO_HUMAN |
| `APPROVAL_CHECK` | approval invalid/expired/mismatched | `FINAL_DECISION`=DENY |
| `FINAL_DECISION` | always | `AUDIT_LOGGED` |
| `AUDIT_LOGGED` | outcome ∈ {ALLOW, ALLOW_WITH_CONSTRAINTS} | `COMMITTED` |
| `AUDIT_LOGGED` | outcome = DENY | `DENIED` |
| `AUDIT_LOGGED` | outcome = ESCALATE_TO_HUMAN | `ESCALATED` |
| `AUDIT_LOGGED` | outcome ∈ {SIMULATE_AND_RETRY, REQUEST_MORE_EVIDENCE} | (terminal-for-episode; return to caller) |

**State diagram:**
```
                ┌────────────┐  malformed/missing required
   RECEIVED ───►│  VALIDATED │──────────────────────────────┐
       │        └─────┬──────┘                               │
 malformed            │ always                               │
       │              ▼                                      │
       │        ┌───────────────┐  hard DENY/FORBID/REQUIRE-fail
       │        │ INVARIANT_CHECK│──────────────────────────┐│
       │        └───┬───────┬────┘                          ││
       │  REQUIRE_SIM│       │ pass / no sim                ││
       │            ▼        ▼                              ││
       │   ┌───────────────┐ ┌──────────────────┐           ││
       │   │SIMULATION_CHECK│ │ CONSEQUENCE_CHECK │          ││
       │   └──┬─────────┬───┘ └──┬─────┬─────┬────┘          ││
       │ sim ok│  sim missing│ auto │ needs│ uncertain/     ││
       │      ▼         │     │ admit│ appr │ evidence gap   ││
       │  (to CONSEQUENCE)│   │      ▼      ▼                ││
       │             (SIMULATE_AND_RETRY) ┌────────────┐     ││
       │                     │            │APPROVAL_CHECK│    ││
       │                     │            └──┬───┬───┬──┘    ││
       │                     │        valid  │ absent│ bad   ││
       │                     │        appr   │       │appr   ││
       │                     ▼               ▼       ▼       ▼▼
       │             ┌───────────────────────────────────────────┐
       └────────────►│               FINAL_DECISION               │
                     └───────────────────────┬───────────────────┘
                                              │ always
                                              ▼
                                       ┌────────────┐
                                       │ AUDIT_LOGGED│
                                       └──┬───┬───┬──┘
                             ALLOW*/  DENY│   │ESC│ retry-class → return to caller
                                          ▼   ▼   ▼
                                   COMMITTED DENIED ESCALATED
```

---

## 6. Decision Outcomes

Exactly six. Each is deterministic given `(envelope, policy_version, evidence)`.

| Outcome | Required conditions | Allowed prior states | Audit requirements |
|---|---|---|---|
| **ALLOW** | all hard invariants pass; `τ(s) ∈ Viab̂(A)` via Tier-1 + trusted Tier-2; no `REQUIRE_APPROVER`; evidence fresh | `CONSEQUENCE_CHECK`, `APPROVAL_CHECK` | full record; note "auto-admitted", policy_version, evidence hashes |
| **ALLOW_WITH_CONSTRAINTS** | as ALLOW but admitted only under narrowed scope/args, time-box, or rate-limit | `CONSEQUENCE_CHECK`, `APPROVAL_CHECK` | record the applied constraints verbatim |
| **SIMULATE_AND_RETRY** | a `REQUIRE_SIMULATION <fidelity>` is unmet or sim below required fidelity | `SIMULATION_CHECK` | record which simulation + fidelity was required |
| **REQUEST_MORE_EVIDENCE** | a `MUST_HAVE`/`REQUIRE_ATTESTATION` or freshness requirement is unmet | `CONSEQUENCE_CHECK`, `INVARIANT_CHECK` | record the missing evidence item(s) |
| **ESCALATE_TO_HUMAN** | uncertain region, `MAX_*` exceeded, `MAX_IRREVERSIBILITY`, `REQUIRE_APPROVER` unresolved, or any advisory escalation | `CONSEQUENCE_CHECK`, `APPROVAL_CHECK` | record trigger + required approver policy |
| **DENY** | any hard `DENY`/`FORBID`/`REQUIRE`-fail, invalid/expired/mismatched approval, or malformed required field | `RECEIVED`, `INVARIANT_CHECK`, `APPROVAL_CHECK` | record the dispositive rule id |

Mapping to `AGENT_ACTION_ADMISSIBILITY_MVP.md` §7 (same six, renamed for the machine contract):
`SIMULATE_AND_RETRY`≡`SIMULATE_OR_REPLAN`, `REQUEST_MORE_EVIDENCE`≡`REQUEST_ADDITIONAL_EVIDENCE`,
`ESCALATE_TO_HUMAN`≡`REQUIRE_HUMAN_APPROVAL`; `ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY` identical.

---

## 7. Simulation Contract

A simulator returns **structured evidence only** — **never a SAFE/UNSAFE verdict**. Required
output fields:

| Field | Type | Meaning |
|---|---|---|
| `coverage` | `float [0,1]` + scope note | fraction/scope of effects the simulator claims to model |
| `confidence` | `float [0,1]` | calibrated where possible |
| `assumptions` | `array<string>` | versions/state/isolation assumed |
| `affected_resources` | `array<string>` | resources the run predicts are touched |
| `predicted_changes` | `array<Effect>` | per-resource predicted change |
| `rollback_confidence` | `float [0,1]` | confidence the declared rollback works |
| `unknown_effects` | `array<string>` | known gaps / unmodeled dependencies |
| `simulation_version` | `string` (semver+hash) | simulator identity + version, for calibration |

**Fidelity classes** (assigned by the gate from coverage/confidence/calibration history, not by
the simulator): `HIGH` (authoritative within covered scope), `MEDIUM` (supporting; needs
corroboration), `LOW`/`UNKNOWN` (annotative only). **LOW/UNKNOWN fidelity MUST NOT independently
authorize a consequential transition.** The gate MUST run **post-commit calibration** (compare
`predicted_changes` vs actual) and down-rate `simulation_version` fidelity on divergence.

---

## 8. Approval Binding

An `Approval` object MUST contain and satisfy:

| Field | Rule |
|---|---|
| `approval_hash` | digest over `{action_hash, policy_hash, approver, scope, exp}` |
| `action_hash` | = `hash(canonical envelope)` (§9); **any envelope change invalidates** |
| `policy_hash` | = digest of `policy_version`; policy change invalidates |
| `approver` | independent principal; **MUST** satisfy SoD (≠ delegator/requester); high-assurance ⇒ N≥2 independent |
| `expiration` | unexpired at decision time; expired ⇒ `DENY` |
| `scope` | the exact operation + target + argument bounds approved; narrower actions inherit, broader do not |
| `revocation` | checked against a revocation list at decision time |
| `replay_prevention` | single-use nonce bound to `action_id`; reuse ⇒ `DENY` |
| `modification_invalidation` | if recomputed `action_hash` ≠ approved `action_hash` ⇒ `DENY` |

Approvals bind to the **canonical action envelope + policy version**, never to a ticket title.
Break-glass approvals are permitted only with stronger post-hoc audit, tighter expiration, and
mandatory review (MVP §8).

---

## 9. Audit Record

Immutable, append-only, signed. **Every** decision (all six outcomes, including retries) MUST
write exactly one record before leaving the gate.

```
AuditRecord {
  record_id            : string (UUID)
  action_id            : string           # from envelope
  action_hash          : hash             # hash(canonical envelope)
  input                : object           # full canonical envelope (or content-addressed ref)
  decision             : enum{ALLOW, ALLOW_WITH_CONSTRAINTS, SIMULATE_AND_RETRY,
                               REQUEST_MORE_EVIDENCE, ESCALATE_TO_HUMAN, DENY}
  reason               : object{rule_id, human_readable}   # dispositive rule / trigger
  evidence             : array<{class, ref, hash, fidelity?}>   # §3 classes consulted
  approver             : object|null       # approval(s) used, if any
  policy_version       : string
  simulation_version   : string|null
  ai_advisory          : object|null       # Tier-3 output if consulted (advisory only, logged)
  applied_constraints  : object|null       # for ALLOW_WITH_CONSTRAINTS
  timestamps           : {received, decided, committed?}
  prev_record_hash     : hash              # hash-chained for tamper evidence
  signature            : string            # signed by the gate's audit key
}
```

The audit chain (`prev_record_hash`) makes the log tamper-evident. `ai_advisory` is recorded for
transparency but is **never** a basis for admission (§3, §12).

---

## 10. Ten Transition Fixtures

Reusing the MVP §10 transitions. Each fixture: input envelope (abbreviated to the discriminating
fields; full schema per §2), expected decision, required evidence, expected audit output.

| # | Operation (input highlights) | Expected decision | Required evidence | Expected audit (`reason.rule_id`) |
|---|---|---|---|---|
| F1 | `IAM_GRANT_ADMIN`, grantee ≠ self, no approval yet | `ESCALATE_TO_HUMAN` | dual-control approver, workload attestation | R2 (`REQUIRE_APPROVER dual_control`) |
| F1b | `IAM_GRANT_ADMIN`, grantee == self | `DENY` | — | R1 (self-grant forbidden) |
| F2 | `DEPLOY`, signed image, canary + retained prev, HIGH dry-run | `ALLOW` (or `ALLOW_WITH_CONSTRAINTS` canary) | signed artifact, HIGH sim, rollback | policy pass; auto-admit |
| F3 | `DB_DELETE`, no verified backup | `DENY` | — | R3 (`MUST_HAVE verified_restorable_backup` unmet → hard) |
| F3b | `DB_DELETE`, verified backup, not last replica | `ESCALATE_TO_HUMAN` (irreversible) | backup+restore proof, dual-control | R3 + `MAX_IRREVERSIBILITY` |
| F4 | `NET_EXPOSE`, widen to public on sensitive tag | `DENY` | — | R4 (sensitive public exposure) |
| F5 | `SECRET_READ`, single, approved sink, approver present | `ALLOW_WITH_CONSTRAINTS` (post-read rotation) | sink approval, single-scope | R6 |
| F6 | `MONITORING_DISABLE`, target = gate audit path | `DENY` | — | R7 (gate audit path forbidden) |
| F7 | `DB_MUTATION`, no simulation attached | `SIMULATE_AND_RETRY` | MEDIUM+ transaction preview | R8 (`REQUIRE_SIMULATION MEDIUM`) |
| F8 | `CLOUD_SPEND_INCREASE`, self-approved | `DENY` | — | R9 (`FORBID self_approved`) |
| F9 | `EXTERNAL_COMMS`, free-text to customers | `DENY` | — | R10 (free-text forbidden) |
| F10 | `KEY_ROTATE`, live dependents, cutover plan present | `ESCALATE_TO_HUMAN` | dependents map, cutover plan, single approver | `REQUIRE_APPROVER single` |

(F1b/F3b included to fixture the deny-vs-escalate branches; the ten operations T1–T10 are all
covered.)

---

## 11. Acceptance Tests

Deterministic conformance tests. Each MUST produce the stated outcome on any conformant gateway.

| # | Test | Setup | Required outcome |
|---|---|---|---|
| A1 | Missing attestation | class `REQUIRE_ATTESTATION`, `attestation` absent | `REQUEST_MORE_EVIDENCE` |
| A2 | Expired approval | valid-shaped approval, `expiration` in past | `DENY` |
| A3 | Policy mismatch | approval `policy_hash` ≠ current `policy_version` | `DENY` |
| A4 | Rollback missing | class `MUST_HAVE verified_restorable_backup`, none | `DENY` (hard) / `REQUEST_MORE_EVIDENCE` if class allows |
| A5 | Simulation unavailable | class `REQUIRE_SIMULATION HIGH`, no sim | `SIMULATE_AND_RETRY` |
| A6 | Stale state | `state_freshness.as_of` beyond class bound | `REQUEST_MORE_EVIDENCE` (fail-to-human if irreversible) |
| A7 | Credential escalation | `credential_scope.permissions` ⊄ delegated authority | `DENY` (privilege monotonicity) |
| A8 | Ticket mismatch | `linked_ticket` self-authored where SoD required | `DENY` |
| A9 | Approval modified | `approval.action_hash` ≠ recomputed `action_hash` | `DENY` |
| A10 | Action modified | arguments changed after approval issued | `DENY` (modification invalidation) |
| A11 | Malformed envelope | required field absent/ill-typed | `DENY` at `VALIDATED` |
| A12 | Advisory cannot admit | hard `REQUIRE_APPROVER` unmet, high AI confidence "safe" | `ESCALATE_TO_HUMAN` (AI cannot admit) |
| A13 | Determinism | identical envelope+policy+evidence submitted twice | identical decision + identical `reason.rule_id` |
| A14 | Audit completeness | any of the six outcomes | exactly one signed, hash-chained `AuditRecord` written |

---

## 12. Extension Points

Extensions plug in as **evidence producers or transport adapters**. Contract:

| Extension | Interface role | May do | May NOT do |
|---|---|---|---|
| Simulation engines | produce §7 reports | add `expected_effects`, coverage, fidelity | assert SAFE/UNSAFE; auto-admit |
| Blast-radius / consequence engines | produce Tier-2 evidence | add reachable-set + coverage | admit beyond the computed bound |
| AI advisors (Tier-3) | produce advisory annotations | identify concerns, **escalate**, propose alternatives | admit, lower assurance, approve, edit policy |
| BCVF (optional) | evidence plugin | add same-latent disagreement signal → escalate | be required; block the gate if absent |
| USE (optional) | evidence plugin | add coordination/humanness signal → escalate | be required; be load-bearing |
| SCC (optional) | evidence plugin | add fusion/contradiction signal → escalate | be required; make the decision |
| MCP adapters | transport | map `tools/call` → envelope | change policy semantics |
| non-MCP adapters (SDK, API-gw, admission ctlr, credential broker) | transport/enforcement | map calls → envelope; enforce credential/egress | change policy semantics |

**Two non-negotiable rules:** (1) **Extensions MAY add evidence.** (2) **Extensions MAY NEVER
bypass deterministic policy** — they cannot admit an action, satisfy a hard requirement, lower
required assurance, or approve. The gate MUST remain fully functional and safe with **all
optional extensions (BCVF/USE/SCC/AI advisor) removed** — this is the standing conformance test.

---

## 13. Versioning

- **Semantic versioning** for three independently-versioned artifacts: the **envelope schema**
  (`schema_version`), the **policy** (`policy_version`), and each **simulator**
  (`simulation_version`). All appear in the audit record.
- **Backward compatibility:** MINOR/PATCH schema changes MUST be additive (new optional fields,
  new operation classes) and MUST NOT alter the meaning of existing fields or the decision for a
  previously-valid envelope. MAJOR bumps may remove/rename fields and require an adapter.
- **Policy migration:** a new `policy_version` is a signed, reviewed artifact in the root-of-
  trust; migrations are staged and rollback-able. In-flight approvals bound to the prior
  `policy_hash` are invalidated (§8) — no silent policy drift under an existing approval.
- **Envelope evolution:** unknown optional fields MUST be preserved and logged (forward-compat);
  unknown **required** fields in a newer schema MUST cause the older gateway to `DENY` (fail-to-
  safe) rather than silently ignore.

---

## 14. Can / Cannot Prove

**Can prove (per implementation, by conformance tests §11):**
- contract compliance (envelope validation, evidence classing);
- deterministic policy evaluation (same inputs → same decision + same dispositive rule);
- auditability (exactly one signed, hash-chained record per decision);
- deterministic behavior of the state machine and outcome mapping.

**Cannot prove (explicitly out of reach):**
- world correctness (that the observed state matches reality);
- complete safety (invariant completeness over the open world);
- perfect consequence prediction (simulators are evidence with coverage limits, §7);
- formal verification of open systems (this uses a **conservative under-approximation** `Viab̂(A)`,
  not a proof — MVP §3, §12; **no novel mathematics is claimed**).

---

## 15. Implementation Order

Conformance is staged; each stage is independently testable and MUST NOT regress the prior.

| Stage | Component | Conformance gate |
|---|---|---|
| 1 | **Envelope validator** | §2 validation rules + A11 |
| 2 | **Policy evaluator** | §4 language + precedence determinism + A13 |
| 3 | **Audit logger** | §9 immutable, hash-chained, signed + A14 |
| 4 | **Simulation integration** | §7 structured evidence + fidelity + A5 |
| 5 | **Human approval** | §8 binding, SoD, replay/mod-invalidation + A2/A3/A9/A10 |
| 6 | **Credential broker** | §9 (MVP) bypass-resistance; enforcement-not-monitoring |
| 7 | **AI advisory (Tier-3)** | escalate-only; A12 (cannot admit) |
| 8 | **Operational evaluation** | MVP §11 baselines + preregistered `Δ_min` kill criterion |

Stages 1–3 constitute the minimum deterministic gate (no AI, no simulation). Stages 4–7 add
evidence and enforcement without changing policy semantics. Stage 8 is the thesis gate.

---

## Validation (performed on this document)

- ✓ **Every field appears exactly once** — §2 is the single canonical enumeration (24 fields,
  numbered, no duplicates); all other sections reference them.
- ✓ **Every state has valid transitions** — §5 transition table covers all 11 states; terminals
  (`COMMITTED`/`DENIED`/`ESCALATED`) and the retry-rest at `AUDIT_LOGGED` are defined.
- ✓ **Every outcome is deterministic** — §6 gives fixed conditions; §4 precedence makes rule
  order irrelevant; A13 asserts reproducibility.
- ✓ **No AI component can approve** — §3, §6, §7, §12, and A12 all forbid AI admission/approval;
  AI is advisory + escalate-only and logged.
- ✓ **No extension bypasses hard policy** — §12 two non-negotiable rules; extensions add evidence
  only.
- ✓ **BCVF/USE/SCC remain optional** — §3 and §12 mark them optional/advisory; gate must work
  with all removed (standing conformance test).
- ✓ **Consistent with `AGENT_ACTION_ADMISSIBILITY_MVP.md`** — §2 MVP crosswalk, §6 outcome
  mapping, and the viability/`Viab̂(A)`, non-compensatory, escalate-only, no-novel-math, and
  Δ_min semantics all match the MVP; nothing is broadened.
