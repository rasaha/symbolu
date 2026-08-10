# ActionGate — Architectural Abstraction

**Status:** architecture study (documentation only). Grounded in the reference implementation
`action_gate_reference/action_gate_ref/` and the runtime `action_gateway/`. Every claim is
tagged **[fact]** (verifiable in code/tests) or **[interpretation]** (architectural reading) or
**[speculative]** (not yet evidenced).

Honesty caveats that bound every statement here: the signing scheme is a **reference HMAC**
stand-in, not production asymmetric PKI (`signing.py`); the audit chain is **tamper-evident,
not tamper-proof, and explicitly not a blockchain** (`audit.py`); the broker mints **no real
secrets** (`broker.py`); version is `0.1.0-ref`. The abstraction below is real; the productized
crypto/key-custody is out of scope in this reference.

## 1. The smallest abstraction underneath the DevOps vocabulary

Stripped of Kubernetes/cloud terms, ActionGate is a **pure decision function wrapped in a
commit protocol**:

```
D(envelope, signed_policy, evidence, approvals, state) -> decision        # pure, deterministic
commit(decision, token) -> executed | rejected                            # once, replay-proof
```

**[fact]** `gate.evaluate(...)` is a pure function of `(envelope, signed_policy, evidence,
approvals, now, used_nonces)` returning a decision dict; it performs no I/O and mutates nothing
(`gate.py`). The runtime (`action_gateway/gateway.py`) records and enforces that decision and
adds the commit machinery; it never overrides the decision.

## 2. The minimal primitives (mapped to code)

| primitive | what it actually is | grounding [fact] |
|---|---|---|
| **canonical action** | a 24-field envelope reduced to a domain-separated hash over a fixed field projection | `schema.REQUIRED_FIELDS`/`OPTIONAL_FIELDS` (19 required + 5 optional); `projection.action_hash` over `PROJECTION_MANIFEST` (includes authorization-relevant fields; excludes `action_id`, `timestamp`, `agent_identity.sig`, `approvals`, `attestation`) |
| **policy** | a signed, hashed bundle of per-operation rules made of a fixed operator set | `policy.build_bundle`/`sign_policy`/`policy_hash`; `DEFAULT_RULES` (R1–R10); operators `DENY/FORBID/REQUIRE/MUST_HAVE/REQUIRE_ATTESTATION/REQUIRE_SIMULATION/REQUIRE_APPROVER/MAX_SCOPE/MAX_COST/MAX_BLAST_RADIUS/MAX_IRREVERSIBILITY/ALLOW/ALLOW_WITH_CONSTRAINTS` |
| **evidence** | structured artifacts bound to the exact action hash, with freshness and fidelity | `evidence.build_evidence` (`bound_to = action_hash`), `verify_binding`, `is_fresh`, `fidelity_at_least`; simulation evidence is **structured only** (no SAFE/UNSAFE boolean) |
| **approvals** | signed multi-party attestations bound to `action_hash` + `policy_hash` + nonce, with SoD and approver-count | `approval.build_approval`/`verify_approval` (action-hash, policy-hash, expiry, nonce-replay, scope-subsumption, SoD, `_APPROVER_MIN`) |
| **state snapshot** | an opaque `current_state_hash` + `state_freshness.as_of` carried in the envelope | envelope fields; `gate._stale` (freshness bound); used again at commit for TOCTOU |
| **transaction boundary** | one request record from submit to a terminal runtime state | `gateway.Record` + `state.py` lifecycle (`PENDING→APPROVED→EXECUTING→COMPLETED/FAILED`, plus `DENIED/ESCALATED/EXPIRED`) |
| **execution token** | a short-lived, gate-signed capability binding the exact action + policy + constraints + decision record | `token.build_token` (payload binds `action_hash`, `permitted_operation`, `permitted_target`, `credential_scope`, `constraints`, `expiration`, `nonce`, `policy_hash`, `decision_record_hash`) |
| **replay protection** | single-use nonces (approval and token) + expiry | `used_nonces` in `gate.evaluate`/`approval.verify_approval`/`token.verify_token`; gateway burns `rec.token_nonce` into `_spent_nonces` after a successful commit |
| **commit-time validation** | full revalidation of the token against the *actual* call at execution time | `token.verify_token`: signature, expiry, nonce-replay, `action_hash` rebind, operation/target subset, argument-bound expansion, policy re-eval, **TOCTOU** state match |
| **audit** | an append-only, hash-chained, self-verifying record set | `audit.build_audit_record` + `AuditChain.append` (re-verifies the whole chain after every append) |

## 3. The non-compensatory decision core

**[fact]** `gate.evaluate` computes the outcome as the **minimum-severity** tier over all matched
effects (`_SEVERITY`: `DENY 0 < REQUEST_MORE_EVIDENCE 2 < SIMULATE_AND_RETRY 3 <
ESCALATE_TO_HUMAN 4 < ALLOW_WITH_CONSTRAINTS 5 < ALLOW 6`). This is a **non-compensatory**
aggregation: no amount of satisfied conditions offsets a single dispositive restriction. Six
frozen outcomes; no probability, no learning, no LLM in the decision path.

## 4. The one domain adapter

**[fact]** The only operation-specific code in the decision core is `gate.extract_facts(envelope)`
— it maps the structured `arguments` dict to a fixed set of boolean/scalar **facts** (self_grant,
last_replica, public_sensitive, affected_count, projected_cost, …). The gate's own comment calls
it "the 'domain adapter' stub." Everything else (`_priv_monotonic`, `_has_evidence`,
`_approver_satisfied`, the operator loop) is operation-agnostic and reads facts + policy only.

**[interpretation]** This is the seam that makes ActionGate a *generic* engine: the decision
logic, hashing, binding, token, and audit are domain-independent; only the **operation
vocabulary + fact extraction + policy rules** are domain data. Changing domains means changing
data and one adapter, not the engine or the security model. (Developed in
`ACTIONGATE_DOMAIN_GENERALIZATION.md`.)

## 5. What the abstraction is NOT (bounding claims honestly)

- **[fact]** Not an identity provider, secret vault, or session proxy — it assumes an
  authenticated principal and a broker; it issues no identities and stores no secrets.
- **[fact]** Not a general policy language — the operator set is fixed (not Rego/Turing-style).
- **[fact]** Not a resource manager — it authorizes and records a commit; it does not itself undo
  a downstream side effect (no compensation engine). Reversibility is *reasoned about*
  (`reversibility`, `rollback_plan`, `MAX_IRREVERSIBILITY`) but not *executed*.
- **[fact]** Not tamper-proof storage and not production crypto (reference HMAC; tamper-evident
  audit).

## 6. One-line abstraction

**[interpretation]** ActionGate is a **deterministic, evidence-bound, commit-time authorization
protocol for discrete high-consequence actions**, in which the decision is a pure function and
the execution is a single, replay-proof, TOCTOU-checked commit — with any planner/LLM kept
strictly outside the trust boundary.
