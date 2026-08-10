# ActionGate — Executive Demonstration

**What this shows:** across five realistic autonomous-agent workflows, ActionGate detected **every
one of twelve injected attacks** — measured by running the real system, not asserted. Each attack is
a failure mode that arises specifically because an *agent* (not a person at a console) is taking
*specific, irreversible actions*, and each is caught at a precise point with a specific reason.

Numbers here are **measured** by `real_world_validation.py` and enforced by a regression test. The
comparisons to other systems reflect their **documented roles**, not tests of their code, and are
stated narrowly.

## The five workflows
1. **GitHub coding agent** deploying a merged PR.
2. **Kubernetes agent** deleting a production database StatefulSet.
3. **ERP agent** committing an over-threshold purchase.
4. **Migration agent** running a database schema change.
5. **Multi-agent pipeline** (build agent → migration agent).

Result: **5/5 legitimate actions committed; 12/12 attacks blocked.**

## The demonstrations — failure → why others miss it → how ActionGate prevented it

Each row is a real attack from the run.

### 1. Replay / duplicated execution (GitHub deploy)
- **What happened:** the same authorized deploy was submitted for execution twice.
- **Why a normal system misses it:** IAM re-authorizes each request against current permissions and
  has no single-use notion; OPA returns a decision per query with no commit state. An identical,
  still-authorized action is simply authorized again. **[documented-role]**
- **How ActionGate prevented it:** the execution token carries a **single-use nonce** burned at
  commit; the replay was rejected with `E_NONCE_REPLAY`. Exactly-once, measured.

### 2. Target substitution (GitHub deploy)
- **What happened:** at execution time the target was swapped from `svc://checkout` to `svc://payments`.
- **Why others miss it:** IAM allows any target within the principal's static permissions; there is
  no binding to the *approved* action. **[documented-role]**
- **How ActionGate prevented it:** the target is part of the **canonical action hash**; the swap
  changed the action's identity → `E_ACTION_HASH_MISMATCH`. You cannot redirect an approval.

### 3 & 5. Stale state and TOCTOU (Kubernetes delete)
- **What happened:** the world changed between the approval to delete and the delete itself (and,
  separately, the decision was attempted on an old state snapshot).
- **Why others miss it:** IAM/OPA/CyberArk authorize against identity/policy, not against a **state
  snapshot** that is re-checked at commit. They have no concept of "the state I approved against has
  moved." **[documented-role]**
- **How ActionGate prevented it:** stale state at decision → `REQUEST_MORE_EVIDENCE`; state drift at
  commit → `E_STALE_STATE`, **before any deletion ran**. Time-of-check/time-of-use is closed.

### 4 & 8. Approval reuse and approval-nonce replay (Kubernetes delete, ERP)
- **What happened:** a valid dual-control approval was reused on a *different* action; and an
  approval was replayed after its nonce was spent.
- **Why others miss it:** IAM/OPA have no native multi-party approval; CyberArk's dual-control
  approves a *privileged session*, not a nonce bound to a specific action hash. **[documented-role]**
- **How ActionGate prevented it:** approvals bind to one `action_hash` + `policy_hash` + single-use
  nonce with separation-of-duties → both were `DENY`ed at decision time.

### 6. Policy update after approval (ERP purchase)
- **What happened:** policy was rotated between approval and commit.
- **Why others miss it:** they have no *prepared-commit token* to become stale — IAM/OPA simply
  re-evaluate the call against whatever policy is current, with no notion of the earlier approval.
  **[documented-role]**
- **How ActionGate prevented it:** the token binds the `policy_hash` it was approved under;
  committing under a different policy → `E_POLICY_MISMATCH`. No silent execution under changed rules.

### 7 & 10. Credential tamper and argument expansion at commit (ERP, migration)
- **What happened:** the executing credential scope was altered, and a migration's row count was
  widened, *after* approval.
- **Why others miss it:** IAM checks the credential's static permissions, not whether it matches an
  *approved* action; the arguments of a specific action are not bound to a prior decision.
  **[documented-role]**
- **How ActionGate prevented it:** credential scope and arguments are both inside the **canonical
  action hash**; any change → `E_ACTION_HASH_MISMATCH`. You cannot escalate or expand what was
  approved.

### 9. Blast-radius over-scope (migration)
- **What happened:** a migration claimed to touch 25,000 rows (over the 10,000 cap).
- **Why others miss it:** IAM has no evidence/simulation-gated escalation; OPA can `deny` on a
  threshold but returns a bare deny, not an evidence-backed human-escalation workflow.
  **[documented-role]**
- **How ActionGate prevented it:** `MAX_SCOPE` → `ESCALATE_TO_HUMAN` — the large migration is routed
  to a human, not auto-run.

### 11 & 12. Cross-step replay and cross-agent action confusion (multi-agent pipeline)
- **What happened:** one agent re-fired another's committed action; and a migration slot was driven
  with a *different* agent's action.
- **Why others miss it:** session/role-based systems do not bind each agent's authorization to a
  specific action instance; a shared or delegated credential could re-drive an action.
  **[documented-role]**
- **How ActionGate prevented it:** each step's token binds only its own action → replay hit
  `E_NONCE_REPLAY`, the action swap hit `E_ACTION_HASH_MISMATCH`. In a multi-agent pipeline, every
  step commits exactly once and only its own action, all under one auditable correlation id.

## The through-line
**[interpretation]** Every one of these failures exists because an autonomous agent takes a
**specific action** that must be **committed once, against the state and policy it was approved
under, with the evidence and approvals that gate it.** Traditional access control answers a
different question — "may this identity, in general, do this class of thing?" — and therefore does
not, by design, catch action-instance replay, retargeting, TOCTOU, stale-policy commits, or
post-approval tampering. ActionGate binds the decision to the exact action and re-validates it at
commit, which is why all twelve were caught.

## Honest scope
- These are **measured** detections against the reference implementation; the signing is a reference
  HMAC stand-in and the audit is tamper-*evident* (production crypto and tamper-*proofing* are out of
  scope in this reference — see the architecture study).
- The comparative claims are **documented-role** characterizations, not tests of IAM/OPA/CyberArk.
- Workflows are realistic narratives mapped onto the frozen operation set; the security mechanisms
  exercised (hashing, binding, token, TOCTOU, approvals) are the real, unmodified ones.

**Bottom line:** for agentic systems that take real actions, ActionGate demonstrably closes a class
of failures that principal/session/decision-layer authorization is not designed to catch — with
every claim here reproducible by running the harness.
