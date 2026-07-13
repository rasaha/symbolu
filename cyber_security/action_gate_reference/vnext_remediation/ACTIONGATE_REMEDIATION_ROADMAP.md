# ACTIONGATE_REMEDIATION_ROADMAP — the safest path to deterministic remediation (vNext)

Status: **DESIGN ONLY.** Sequencing so each step is additive, reversible, and gated on the
two compatibility invariants (hash-invariance, decision-invariance). No implementation here.

## Guiding constraints (unchanged from the brief)
- Decision stays `D(envelope, signed_policy, evidence, approvals, state)`; LLMs outside the
  trust boundary.
- No DENY weakened; no DENY silently made retryable; no probabilistic logic; no AI in the gate;
  no policy-semantics change; six outcomes preserved.

## Phase 0 — Derive-only, internal (no wire change)
- Implement `derive_remediation(decision, envelope, signed_policy, evidence, approvals)` as a
  pure read-only function beside the gate. Not returned on the wire yet.
- Add conformance tests: **hash-invariance** and **decision-invariance** over the full existing
  vector set; assert `derive_remediation` never runs before or feeds into `D`.
- Add the "DENY ⇒ every required_change is TERMINAL/IMPOSSIBLE with no retry token" test.
- **Exit criterion:** both invariants green; remediation reproducible from `(audit record,
  signed policy)`.
- **Risk:** none on the wire (nothing exposed).

## Phase 1 — Expose `required_changes[]` additively at disclosure STANDARD
- Add the optional `remediation` object to the response (schema §1 of the schema doc), behind a
  caller capability flag; default disclosure **STANDARD** for authenticated first-party, **NONE**
  otherwise.
- Ship as **SemVer MINOR**; no policy re-sign, no edited golden hashes; add *new* vectors for
  reason codes / classes / disclosure redaction.
- CLI `--explain`, SDK optional field, MCP capability.
- **Exit criterion:** old vectors unchanged; new vectors green; red-team confirms disclosure
  cannot be self-escalated and NONE omits the block.
- **Risk:** information disclosure — bounded by disclosure default and value-redaction below FULL.

## Phase 2 — `all_unmet_conditions[]` at FULL + retry governance/accounting
- Expose `all_unmet_conditions[]` **only** at disclosure FULL (constraint-fishing containment).
- Implement broker-side governance (stateless gate unchanged): per-`correlation_id` max
  attempts, budget, timeout, loop/duplicate detection, `used_nonces` accounting, strictly-
  changing-`action_hash` enforcement on retries.
- **Exit criterion:** DoS controls demonstrably cap attempts/cost; nonce/expiry/binding replay
  tests pass (they already hold in the gate; here we test the broker wraps them correctly).
- **Risk:** oracle/DoS — bounded by FULL-gating and broker caps.

## Phase 3 — External planner interface
- Define the planner ↔ broker ↔ gate contract (sequence diagrams in the retry-architecture
  doc): planner reads remediation, builds a *new* action (new `action_hash`), resubmits;
  broker enforces governance; gate re-evaluates purely.
- Provide a planner SDK surface that forwards evidence/approvals for **re-verification** (never
  trusts the planner) and refuses to raise its own disclosure.
- **Exit criterion:** end-to-end tests show a planner can converge multi-step *without* ever
  altering a decision, and a malicious planner can at most waste bounded budget.
- **Risk:** loop amplification — bounded by Phase 2 governance.

## Phase 4 (optional, future major) — reconsider a seventh outcome
- Only if operational evidence shows payload enrichment is insufficient. Any seventh outcome
  must be a **new terminal state that never relaxes an existing DENY/ESCALATE**, gated behind a
  **MAJOR** version with re-issued conformance goldens. This milestone recommends **not** doing
  this.

## Rollback posture
Every phase is behind a capability flag / disclosure setting and touches no hashed surface, so
each is independently revertible by turning the flag off — with zero effect on decisions or
audit continuity.

---

## The five conclusion answers (explicit)

1. **Is `required_changes[]` worth implementing?**
   **Yes.** It is a deterministic, audit-neutral (excluded from every hash), additive
   re-projection of the evaluation the gate already performs. It removes blind retries and
   enables an external planner with zero cost to decision purity. Ship it in Phase 1 behind
   disclosure control.

2. **Should `all_unmet_conditions[]` be exposed?**
   **Yes, but only at disclosure FULL**, with `dispositive_rules` retained as the single audit
   anchor. It is deterministic and additive; its sole risk (constraint fishing) is contained by
   restricting it to trusted FULL callers (Phase 2).

3. **Should the current six outcomes remain unchanged?**
   **Yes.** They already partition the remediation space; changing them would alter decision
   semantics (e.g. softening `MAX_*`/`REQUIRE_APPROVER` ESCALATE into a self-service retry) and
   break the schema, state machine, and conformance vectors.

4. **Is a seventh outcome justified?**
   **No — Recommendation A (payload enrichment only).** Modification-retryability is a property
   of a `required_change` (`RETRYABLE_BY_ACTION_MODIFICATION`), not a new decision. A seventh
   outcome would be a decision-semantics change and a MAJOR compatibility break for no gain.

5. **What is the safest roadmap?**
   The additive, disclosure-defaulted, invariant-gated phases above: **Phase 0** derive-only
   with hash/decision-invariance proofs → **Phase 1** expose `required_changes[]` at STANDARD
   (SemVer MINOR) → **Phase 2** `all_unmet_conditions[]` at FULL + broker governance →
   **Phase 3** external planner — each behind a capability flag, none touching a hashed surface,
   each independently revertible. Defer any seventh outcome indefinitely.
