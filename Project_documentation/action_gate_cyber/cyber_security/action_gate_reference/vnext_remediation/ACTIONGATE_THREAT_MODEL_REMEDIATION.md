# ACTIONGATE_THREAT_MODEL_REMEDIATION — disclosure levels & new attack surfaces (vNext)

Status: **DESIGN ONLY.** The remediation layer turns the gate into a richer *oracle*. This
document scopes the new surface and the controls that bound it. Baseline invariants (I1–I3
in `ACTIONGATE_REMEDIATION_DESIGN.md`) mean no attack here can produce an ALLOW that `D` would
not already produce for the same inputs; the residual risk is **information disclosure** and
**resource exhaustion**, not authorization bypass.

## 1. Disclosure levels (Design Q4)

Remediation verbosity is a per-caller, policy-set trust parameter. It changes only *what is
reported*, never the decision.

| level | `outcome` + `dispositive_rules` | `required_changes[]` | `all_unmet_conditions[]` | typical caller |
|---|---|---|---|---|
| **FULL** | yes | full, with exact targets (kinds, fidelities, thresholds, approver policy, facts) | yes | first-party planner in a trusted control plane |
| **STANDARD** | yes | dispositive tier only; class + coarse target (e.g. "evidence required" without listing every accepted kind) | no | first-party agent, authenticated |
| **MINIMAL** | yes | class only, no targets (e.g. `RETRYABLE_BY_EVIDENCE`) | no | semi-trusted internal automation |
| **NONE** | yes | omitted | omitted | third-party / untrusted agents; external callers |

Rules:

- `outcome` and `dispositive_rules` are **always** returned (they are the existing contract
  and already audited). Disclosure only governs the *added* remediation block.
- Default is **STANDARD** for authenticated first-party callers; **NONE** for anyone else.
  `FULL` is opt-in and should be confined to a trusted planner that already has read access to
  the policy bundle (for which remediation leaks nothing new).
- Disclosure is chosen by the *broker/policy* per authenticated caller identity — never by the
  requesting agent (an agent must not raise its own disclosure).

### Attack analysis of disclosure

- **Policy-oracle attack.** By probing actions and reading `required_changes`, a caller can
  reconstruct the policy's structure (which operators guard which operation, thresholds,
  accepted evidence kinds). At `FULL` this is near-complete disclosure — acceptable only where
  the caller could read the signed policy anyway. `STANDARD` hides exact accepted-kind lists
  and other-tier conditions; `MINIMAL` hides targets; `NONE` collapses the oracle to the
  pre-existing six-way outcome (which already leaks a little and always has).
- **Prompt probing / LLM elicitation.** An LLM agent may try to elicit `FULL` detail via
  crafted requests. Because disclosure is bound to the *authenticated broker-side identity*,
  not to request content, prompt text cannot raise disclosure. The gate ignores natural
  language entirely.
- **Red-team implications.** Red teams should treat `FULL`/`STANDARD` as a documented policy
  side-channel and test that (a) disclosure cannot be self-escalated, (b) `NONE` truly omits
  the block, and (c) remediation never contradicts the outcome (never hints a DENY is
  retryable). These become conformance assertions.
- **First-party planner use.** `FULL` is designed for this: a trusted planner needs exact
  targets to build a correct next action in one shot, minimizing attempts (which *reduces* DoS
  surface). The planner already operates inside the policy trust domain.
- **Third-party agent use.** Default **NONE**. A third-party agent gets the outcome and may
  retry blindly under the broker's attempt/budget caps, but receives no policy structure.

## 2. New attack surfaces (Design Q7)

For each: **risk → impact → mitigation.** "Mitigation already present" flags controls that
exist in the current code and require no change.

### 2.1 Policy probing
- **Risk.** Systematic submission to map rules/thresholds/accepted kinds from remediation.
- **Impact.** Disclosure of policy structure; enables targeted constraint-fishing. No bypass.
- **Mitigation.** Disclosure levels (default STANDARD/NONE); per-identity rate limits; the
  policy is signed and versioned so structure is not itself a secret, only its convenience.
  Optionally log high-entropy probing per `correlation_id`/identity.

### 2.2 Retry DoS
- **Risk.** Flooding the gate/broker with attempts or forcing expensive evidence/simulation
  generation.
- **Impact.** Resource exhaustion; no authorization impact (gate is pure, cheap, stateless).
- **Mitigation.** Broker **max attempts**, **budget**, **timeout**, **loop/duplicate
  detection** (`ACTIONGATE_RETRY_ARCHITECTURE.md` §2); idempotent caching on identical
  `action_hash`. The gate itself has no unbounded work.

### 2.3 Gradient attacks
- **Risk.** Using remediation as a fitness signal to hill-climb toward ALLOW (e.g. binary-
  searching a `MAX_COST`/`MAX_SCOPE` threshold).
- **Impact.** Learns thresholds faster than black-box probing. Still cannot exceed policy —
  the ALLOW it may find is a genuinely-compliant action, which is the *intended* behavior.
- **Mitigation.** For thresholds, this is acceptable (a compliant smaller action is fine).
  Guard against it *revealing* thresholds precisely by returning `current`/`limit` only at
  `FULL`; at `STANDARD` return class without the numeric limit. Non-compensatory dominance
  means the attacker cannot climb past a co-present DENY/ESCALATE.

### 2.4 Constraint fishing
- **Risk.** Enumerating `all_unmet_conditions[]` to discover every guard at once.
- **Impact.** Full per-operation policy disclosure in one call.
- **Mitigation.** `all_unmet_conditions[]` is **FULL-only**. At STANDARD and below only the
  dispositive tier is shown, so guards are revealed one dominance layer at a time (and each
  modification is a fresh action, so there is no cheap accumulation).

### 2.5 Partial remediation abuse
- **Risk.** Satisfy the cheap retryable layer, hoping the gate "remembers progress" and lets
  the action through with the harder layers unmet.
- **Impact.** Would be catastrophic if the gate accumulated state — but it does not.
- **Mitigation.** **Non-compensatory, stateless evaluation.** Every submission is scored fully
  from scratch; a satisfied REQUEST_MORE_EVIDENCE does not lower a co-present ESCALATE/DENY.
  `satisfies_alone:false` in the schema communicates this. Mitigation already present.

### 2.6 Credential replay
- **Risk.** Reuse a credential/delegation from an authorized action on a different one.
- **Impact.** Privilege escalation if unbound.
- **Mitigation.** `credential_scope` + `delegation_chain` are in the `action_hash` projection
  and re-checked by `PRIV_MONO`; a different credential is a different action. Mitigation
  already present.

### 2.7 Approval replay
- **Risk.** Reuse a valid approval on a modified/expired/other action.
- **Impact.** Unauthorized approval.
- **Mitigation.** `approval.verify_approval` binds `action_hash`+`policy_hash`+`nonce`+
  `expiration`+scope+SoD; `E_ACTION_HASH_MISMATCH`/`E_POLICY_MISMATCH`/`E_EXPIRED`/
  `E_NONCE_REPLAY`/`E_SCOPE_VIOLATION` fail closed. Mitigation already present; remediation
  never suggests reusing an approval (row 6 is TERMINAL).

### 2.8 Loop amplification
- **Risk.** A planner ↔ gate loop that never converges, each turn spawning evidence/sim work.
- **Impact.** Cost amplification.
- **Mitigation.** Broker loop detection (reject unchanged-`action_hash` re-submits), attempt/
  budget/timeout caps, and — for planner loops — a required strictly-changing `action_hash`
  per attempt. The gate cannot be looped into any authority.

### 2.9 Information leakage
- **Risk.** Remediation reveals sensitive internal facts (e.g. that a target is "sensitive",
  or exact cost/blast values).
- **Impact.** Confidential-context disclosure.
- **Mitigation.** Disclosure levels; redact fact *values* below FULL (return the fact *name*
  and class, not `current` values); never echo raw envelope contents in remediation — only the
  policy-derived condition. `remediation` is excluded from the audit hash, so it is a
  transport concern, not a durable disclosure.

## 3. Invariants the threat model relies on (all already true in code)

- `D` is a pure function of `(envelope, signed_policy, evidence, approvals, state)`; remediation
  is computed after and fed back nowhere.
- Every authority artifact is cryptographically bound to `action_hash`/`policy_hash`/`nonce`;
  modification or reuse fails closed.
- Evaluation is non-compensatory and stateless — no partial-progress accumulation.
- The outcome set is unchanged; remediation cannot relabel a DENY/ESCALATE as retryable.

## 4. Net assessment

The remediation layer adds an **information-disclosure** surface (bounded by disclosure levels)
and a **resource-exhaustion** surface (bounded by broker governance). It adds **no
authorization-bypass** surface, because it only reads inputs already adjudicated and hashed and
never participates in `D`. Shipping at default disclosure **STANDARD** (first-party) / **NONE**
(third-party), with `all_unmet_conditions[]` restricted to **FULL**, keeps the oracle within
what a policy-bundle reader already knows.
