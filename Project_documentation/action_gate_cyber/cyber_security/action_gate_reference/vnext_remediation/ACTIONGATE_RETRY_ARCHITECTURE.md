# ACTIONGATE_RETRY_ARCHITECTURE — retry classification, governance, hash evolution (vNext)

Status: **DESIGN ONLY.** Grounded in `gate.py`, `projection.py`, `evidence.py`,
`approval.py`, `schema.py`.

Central principle: **there is no in-gate "retry".** ActionGate is stateless and pure. What a
caller experiences as a "retry" is *the submission of a new action* (new envelope → new
`action_hash`) that is evaluated from scratch. "Retry classification" therefore describes
whether a *new, corrected action* could clear a given condition — never a mutable per-action
state inside the gate.

## 1. Retry classification matrix (Design Q3)

Classification is a function of **(operator, the outcome it produced, hard flag)** — not the
operator alone, because the same operator is terminal or retryable depending on context. The
canonical example: `MUST_HAVE` is `RETRYABLE_BY_EVIDENCE` when soft (→ REQUEST_MORE_EVIDENCE)
but `IMPOSSIBLE` when `hard:true` (→ DENY, e.g. DB_DELETE backup).

| # | condition (operator / check) | outcome tier | retry class | how a *new* action clears it |
|---|---|---|---|---|
| 1 | `MUST_HAVE` (soft) | REQUEST_MORE_EVIDENCE | **Retryable by evidence** | attach fresh evidence of `kind`, `bound_to` the new action_hash, unexpired |
| 2 | `MUST_HAVE` (`hard`) | DENY | **Impossible** (terminal) | not clearable for this action; a different reversible action is a new action |
| 3 | `REQUIRE_ATTESTATION` | REQUEST_MORE_EVIDENCE | **Retryable by evidence** | present unexpired attestation of `attn_type` |
| 4 | `REQUIRE_SIMULATION` | SIMULATE_AND_RETRY | **Retryable by simulation** | attach structured simulation evidence ≥ `min_fidelity`, bound to new action_hash |
| 5 | `REQUIRE_APPROVER` (absent) | ESCALATE_TO_HUMAN | **Human only** | obtain N valid approver signatures binding new action_hash+policy_hash+nonce |
| 6 | `REQUIRE_APPROVER` (present, invalid) | DENY | **Terminal** | an invalid/expired/replayed/mis-scoped approval is a hard fail; a *fresh valid* approval is part of a new action, not a retry of this DENY |
| 7 | `MAX_SCOPE` / `MAX_COST` / `MAX_BLAST_RADIUS` | ESCALATE_TO_HUMAN | **Retryable by action modification** *or* **Human only** | reduce the offending fact below `limit` (new action) **or** obtain a human approver |
| 8 | `MAX_IRREVERSIBILITY` | ESCALATE_TO_HUMAN | **Retryable by action modification** *or* **Human only** | target a reversible resource / add a rollback plan that lowers reversibility class **or** human approver |
| 9 | `FORBID` (fact true) | DENY | **Terminal** | the action as posed is forbidden; only a materially different, non-forbidden action exists |
| 10 | `REQUIRE` (fact false) | DENY | **Terminal**, or **Retryable by action modification** iff the fact is a truthfully-settable argument | set the argument truthfully in a new action (never fabricate) |
| 11 | `PRIV_MONO` (privilege non-monotonic) | DENY | **Impossible** | a credential covering the permission is a *different credential_scope* = a different action |
| 12 | `TICKET_SOD` (self-authored ticket) | DENY | **Terminal** | a ticket authored by another party is a different envelope |
| 13 | `FRESHNESS` (stale state) | REQUEST_MORE_EVIDENCE | **Retryable by evidence** | resubmit with a fresh `state_freshness.as_of` within `freshness_bound_seconds` |

Rows 2, 6, 9, 11, 12 are the DENY-terminal set: invariant **I3** forbids ever emitting a
retry token for them. Rows 7, 8, 10 are dual-class: the gate does **not** choose for the
caller; it lists both `ACTION_MODIFICATION` and `HUMAN_ONLY` options and leaves the decision
to the (human or planner) caller — while the outcome stays ESCALATE_TO_HUMAN.

## 2. Retry governance (Design Q5)

Because the gate is stateless, retry governance lives in the **calling surface / broker**
(SDK, CLI, MCP server, gateway) — never inside `D`. The governance state is keyed by
`correlation_id` (a stable field already in the envelope and the `action_hash` projection),
which lets a broker group the attempts of one logical objective without the gate holding
state.

| control | definition | where enforced | interaction with the gate |
|---|---|---|---|
| **max attempts** | hard cap on submissions per `correlation_id` (e.g. 5) | broker | none — gate re-evaluates each independently |
| **budget** | cumulative cost cap (evidence generation, simulation runs, approver asks) per `correlation_id` | broker | none |
| **timeout** | wall-clock window after which the `correlation_id` is closed | broker | none |
| **loop detection** | reject a submission whose `action_hash` matches a prior *unchanged-and-rejected* attempt in the same `correlation_id` | broker | uses `action_hash` from the gate; no gate change |
| **duplicate detection** | idempotency: identical `action_hash` + identical evidence/approval set → return the cached prior decision, do not re-run side effects | broker | gate is pure, so re-running is safe; caching is an optimization |
| **action hash evolution** | every corrected attempt MUST produce a new `action_hash`; a broker rejects a "retry" whose `action_hash` is unchanged from a rejected attempt | broker | see §3 |
| **credential invalidation** | if `credential_scope` / `delegation_chain` changed between attempts, it is a new action (new `action_hash`) and must re-satisfy `PRIV_MONO` | gate (already) | automatic via projection |
| **approval invalidation** | approvals bind `action_hash`+`policy_hash`+`nonce`; any of: action change, policy rotation, expiry, or nonce reuse invalidates them | gate (already, `approval.verify_approval`) | automatic |
| **simulation replay** | simulation evidence binds `action_hash` and has `valid_until`; it cannot be replayed onto a modified action or after expiry | gate (already, `evidence.verify_binding`+`is_fresh`) | automatic |

Key point: the **security-relevant** governance (approval/credential/simulation invalidation,
replay) is *already enforced by the gate's binding checks*. The broker-side controls (attempts,
budget, timeout, loop/duplicate detection) are DoS/quality-of-service controls and hold no
authority — they can only make the gate run *fewer* times, never approve anything.

### `used_nonces` accounting
`gate.evaluate` takes `used_nonces` and `approval.verify_approval` raises `E_NONCE_REPLAY`
on reuse. The broker maintains the `used_nonces` set per policy epoch. On a genuine retry the
caller must mint a **new approval with a new nonce** bound to the **new action_hash**; a
replayed nonce or a stale-action approval fails closed. This is the anti-replay backbone of
retry governance and requires **no gate change**.

## 3. Action-hash evolution & why replay stays impossible (Design Q6)

`projection.action_hash` digests the JCS-canonical projection of every
**authorization-relevant** field: `agent_identity.{id,key_id}`, runtime, model_provider,
delegator, delegation_chain, objective, tool, operation, target_resource, **arguments**,
**credential_scope**, **current_state_hash**, **state_freshness**, **reversibility**,
policy_version, correlation_id, sequence_id (+ optional rollback_plan, linked_ticket,
expected_effects-by-digest). It **excludes** action_id, timestamp, agent signature, approvals,
and attestation (see `PROJECTION_MANIFEST`).

Consequence: **any remediation that changes an authorization-relevant field changes
`action_hash`.** Reduce `affected_count`, pick a reversible `target_resource`, narrow
`credential_scope`, refresh `state_freshness`, add a `rollback_plan` — each yields a *new*
action identity. What binds to the old identity does not transfer:

- **Approval binding.** `approval.verify_approval` recomputes `action_hash` from the *new*
  envelope and requires `approval.payload.action_hash == action_hash`; otherwise
  `E_ACTION_HASH_MISMATCH`. It also checks `policy_hash` (→ `E_POLICY_MISMATCH` on rotation),
  `expiration` (→ `E_EXPIRED`), `nonce` vs `used_nonces` (→ `E_NONCE_REPLAY`), constraint
  equality, scope subsumption, signature validity, and SoD/approver-count. **A retry cannot
  reuse a prior approval** unless the action is byte-identical, the policy is unchanged, it is
  unexpired, and the nonce is unused — i.e. it was never actually consumed.
- **Credential binding.** `credential_scope` and `delegation_chain` are in the projection, so
  a changed credential is a new `action_hash`, and `PRIV_MONO` re-checks that the new
  permissions are covered by delegation grants. You cannot "carry over" authority.
- **Simulation / evidence binding.** `evidence.verify_binding` requires
  `evidence.payload.bound_to == action_hash`; `is_fresh` requires `now < valid_until`. A
  modified action (new hash) rejects all prior simulation/evidence; an expired one rejects on
  freshness. Simulation is additionally **structured-only** (no SAFE/UNSAFE boolean) so it
  cannot be forged into a verdict.
- **State binding.** `current_state_hash` and `state_freshness` are in the projection; a
  world that moved on produces a different hash and, if stale, trips `FRESHNESS`.

**Replay-impossibility argument (informal proof).** Let A be a prior action with hash `h_A`
and let R be a "retry" that changes any authorization-relevant field. Then
`action_hash(R) = h_R ≠ h_A` (collision resistance of the domain-separated digest). Every
authority artifact X (approval, simulation, evidence) carries an explicit binding
`X.bound_to`/`X.action_hash = h_A`. Verification of X against R requires `X.binding == h_R`,
which is false, so X is rejected (`E_ACTION_HASH_MISMATCH` / `E_EVIDENCE_BINDING`).
If instead R changes *nothing* authorization-relevant (`h_R = h_A`), then R **is** A: nonce
reuse (`E_NONCE_REPLAY`) and expiry (`E_EXPIRED`) prevent re-consumption of a spent approval,
and evidence freshness (`valid_until`) prevents replay of a stale simulation. In both cases
no artifact minted for one action authorizes a different one, and no spent artifact is
reusable. ∎ (This holds under the existing code; the remediation layer adds nothing that
could weaken it, because it only *reads* the same fields.)

## 4. External planner interaction (Design Q10)

The planner (which may be an LLM) sits **entirely outside the trust boundary**. It reads
remediation, proposes a new action, and resubmits. It never sees or influences `D`.

### 4.1 Single corrected retry (evidence)

```
Agent/Planner            Broker (governance)            ActionGate D (pure)
    |                         |                                |
    |  submit action A ------>|  attempts++, check budget ---->|  evaluate(env_A, policy, ev=[], ap=[])
    |                         |<------------------------------ |  outcome=REQUEST_MORE_EVIDENCE
    |                         |                                |  remediation.required_changes=[R2:MUST_HAVE
    |<-- decision + remediation (disclosure-gated) -----------|    -> RETRYABLE_BY_EVIDENCE kind=signed_artifact
    |                         |                                |     bound_to=h_A]
    | (planner reads remediation, obtains a signed_artifact bound to the NEW action)
    | build action A' (== A here; evidence added) ; h_{A'} == h_A only if action unchanged
    |  submit A' + evidence ->|  loop/dup check on h_{A'} ---->|  evaluate(env_{A'}, policy, ev=[art], ap=[])
    |                         |                                |  verify_binding(art, h_{A'}) OK, fresh OK
    |<-- outcome=ALLOW (or next dispositive tier) ------------|  outcome depends ONLY on inputs to D
```

The planner's only power is to assemble inputs; the outcome is still `D`'s pure function of
them. If the planner lies (attaches evidence bound to a different action), `verify_binding`
rejects it — the gate does not trust the planner.

### 4.2 Modification retry (scope reduction) — new action identity

```
Planner                 Broker                        ActionGate D
   | submit DB_MUTATION affected_count=25000 -------->| evaluate -> ESCALATE_TO_HUMAN
   |<- remediation: R7:MAX_SCOPE, class=ACTION_MODIFICATION, limit=10000, current=25000
   | (planner builds a DIFFERENT action: affected_count=9000)
   |   -> env changes -> action_hash h' != h  (projection includes arguments)
   | submit A'(9000) ------------------------------->| evaluate(env', ...) fresh, no carried state
   |<- outcome = ALLOW_WITH_CONSTRAINTS {in_transaction:true} (R7 ALLOW_WITH_CONSTRAINTS branch)
```

The 25000-action's ESCALATE is untouched and audited; the 9000-action is a *separate* audited
decision. No state, evidence, or approval flows between them — there is nothing to replay.

### 4.3 The planner boundary (must-hold properties)

- The planner receives only `remediation` (disclosure-gated) and the public decision fields.
- The planner cannot supply anything that bypasses binding: evidence/approvals it forwards are
  re-verified against the new `action_hash` by the gate.
- The planner cannot influence severity precedence, rule selection, or thresholds — those come
  only from the signed policy.
- A malicious planner can, at worst, waste attempts/budget (a DoS bounded by §2 controls) or
  probe the policy (bounded by disclosure levels in the threat model) — it can never obtain an
  ALLOW that `D` would not have produced for the exact inputs.
