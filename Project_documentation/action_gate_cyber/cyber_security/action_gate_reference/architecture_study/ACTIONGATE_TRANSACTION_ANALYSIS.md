# ActionGate — Transaction-Processing Analysis

**Status:** architecture study (documentation only). The question: does ActionGate resemble
**database transaction processing** more than traditional IAM, and do the classic transaction
verbs map to real mechanisms? Rule: **map only genuinely equivalent concepts; flag every partial
or absent mapping.** **[fact]** = code-grounded, **[interpretation]** = reading, **[gap]** = the
analogy does not hold.

## 1. Does it resemble transaction processing more than IAM?

**[interpretation] Yes, for the runtime; partly for the core.** The *decision core*
(`gate.evaluate`) is an authorization function (IAM-like in role). But the *runtime*
(`action_gateway/gateway.py` + `token.py`) is built like a **commit protocol**: a request has an
identity (`action_hash`), a validate phase, a prepared authorization (token), a single guarded
commit, and a durable log. Traditional IAM has none of: a per-action transaction identity, a
prepared-commit token, commit-time revalidation, single-use nonces, or a TOCTOU state check. Those
are transaction-processing constructs, and ActionGate has them **[fact]**.

## 2. Verb-by-verb mapping (only genuine equivalences)

### BEGIN — **genuine [fact]**
`gateway.submit_action(req)` opens a request: builds the envelope, computes `action_hash`
(`projection.action_hash`), and stores a `PENDING` `Record`. This is the transaction's identity and
start. The `action_hash` is a stable **transaction id derived from content**, not a counter.

### VALIDATE — **genuine [fact]**
`gate.evaluate` runs the decision state machine (`state_trace`: `RECEIVED → VALIDATED →
INVARIANT_CHECK → SIMULATION_CHECK → CONSEQUENCE_CHECK → APPROVAL_CHECK → FINAL_DECISION →
AUDIT_LOGGED`). Schema validation, policy-signature verification, hard invariants, and operator
evaluation all occur here. This is a real VALIDATE phase — and, unlike a DB, it validates against
**external evidence and approvals**, not just internal constraints.

### LOCK — **partial [interpretation]/[fact]; do not overstate**
Two mechanisms together approximate isolation, but neither is pessimistic row-locking:
- **[fact]** A process-level mutex: `gateway._lock` (an `RLock`) serializes evaluate/execute so a
  token nonce is reserved atomically — the code comment states it "guarantees at most one commit
  under parallel duplicate execution." This is a **critical section around commit**, i.e.
  serialization of the commit point, not data locking.
- **[fact]** Optimistic concurrency via `current_state_hash`: the token is bound to the state the
  action was approved against; `token.verify_token` rejects on `StaleStateError` if the observed
  state changed (TOCTOU). This is **MVCC-style validation (optimistic), not locking**.

**[gap]** There is no lock manager, no lock table, no deadlock handling, and no holding of locks
across the transaction — because ActionGate governs a *single* action and does not manage the
underlying resource. The honest mapping is: **LOCK ≈ (serialized commit critical section) +
(optimistic state-hash validation)**, not classical locking.

### PREPARE — **genuine [fact]**
On `ALLOW`/`ALLOW_WITH_CONSTRAINTS`, the gateway mints a signed **execution token**
(`token.build_token`) binding `action_hash`, `permitted_operation`, `permitted_target`,
`credential_scope`, `constraints`, `expiration`, `nonce`, `policy_hash`, and
`decision_record_hash`, and writes the decision to the audit chain. This is a real PREPARE: the
decision is durably recorded and a single artifact authorizes exactly one commit — analogous to a
2-phase-commit **prepared** vote / a write-ahead intent record. (It is a *local* prepare, not a
distributed-2PC coordinator across multiple resource managers — see §3.)

### COMMIT — **genuine [fact]**
`gateway.execute_action` is the commit point:
1. `token.verify_token` revalidates against the **actual** call (signature, expiry, nonce-replay,
   `action_hash` rebind, operation/target subset, argument-bound expansion, policy re-eval, TOCTOU
   state) — a full **commit-time revalidation**;
2. the broker issues a scoped, short-lived credential bound to the verified token;
3. the adapter executes;
4. the token nonce is **burned** into `_spent_nonces` (single-use → **exactly-once**, replay
   rejected henceforth);
5. an `EXECUTED` audit record with the result hash is appended and the chain re-verified.

The nonce burn + audit append is the **commit marker**. Replay after commit fails on
`NonceReplayError`. This is genuine exactly-once commit semantics.

### ROLLBACK — **partial, and mostly [gap]; do not stretch**
- **[fact] Pre-commit abort is clean and real.** A `DENY`, expiry, TOCTOU mismatch, or token
  failure rejects **before** the adapter runs, so there is **no external side effect** to undo — an
  atomic abort. On adapter exception the request moves to `FAILED` and an `EXECUTION_FAILED` audit
  record is written.
- **[gap] Post-commit compensation is out of scope.** ActionGate does **not** undo a side effect
  that a downstream adapter already applied. It has no compensation/undo engine. It *reasons about*
  reversibility (`reversibility`, optional `rollback_plan`, operator `MAX_IRREVERSIBILITY`) and can
  **refuse** or **escalate** irreversible actions, but it does not **execute** a rollback. True
  rollback requires the downstream resource to be transactional or the caller to supply a
  compensating action (itself a new ActionGate transaction).

**Honest ROLLBACK mapping:** ActionGate provides **atomic pre-commit abort** and **reversibility-
aware refusal**, not resource rollback. It is a **commit authorizer/coordinator, not a resource
manager.**

## 3. Where the DB analogy stops (explicit limits)

- **[gap] Not ACID over external state.** ActionGate guarantees properties of the *authorization
  decision and its commit record* (deterministic, replay-proof, audited), not
  Atomicity/Isolation/Durability of the *downstream resource's* data.
- **[gap] Not distributed 2PC.** The token is a *local* prepare/commit for one action against one
  broker/adapter; there is no coordinator driving multiple resource managers to a joint commit.
- **[gap] No concurrency scheduler / serializability proof.** Isolation is a single commit mutex +
  optimistic state check, not a scheduler producing serializable histories over shared data.
- **[fact] Durability is of the audit record**, and the audit is tamper-*evident*, not
  tamper-*proof* (`audit.py`) — a WAL-like append-only log, not a replicated durable store in this
  reference.

## 4. The accurate transaction framing

**[interpretation]** ActionGate implements the **BEGIN / VALIDATE / PREPARE / COMMIT** spine of
transaction processing faithfully, with **LOCK** reduced to a commit critical-section plus
optimistic (MVCC-style) state validation, and **ROLLBACK** limited to atomic pre-commit abort plus
reversibility-aware refusal. It is best read as a **single-action commit protocol with evidence-
bound authorization** — a "one-shot prepared commit" — rather than a general transaction manager
with locking, distributed 2PC, and resource rollback. That distinction is exactly why "AI
Transaction Manager" is *partly* right and *partly* an overstatement (see
`ACTIONGATE_RESEARCH_POSITION.md` §category).
