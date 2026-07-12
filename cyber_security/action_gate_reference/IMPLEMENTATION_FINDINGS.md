# Implementation Findings — Action Gate Reference Harness (Stage 1)

This document records every place where implementing the frozen contracts
surfaced a contradiction, an under-specification, or a decision the specs did
not settle. Per the project integrity rule, the reference implementation does
**not** silently patch the frozen specs; it records the divergence here and
implements the fail-closed reading, isolating the effect to the decision layer
only (never to hash/approval/canonicalization semantics).

Frozen sources referenced:
- `../ACTION_GATE_SPECIFICATION.md` (interface contract; six outcomes; state machine; operators)
- `../ACTION_CANONICALIZATION_AND_HASHING_SPEC.md` (byte-level canonicalization + hashing)
- `../AGENT_ACTION_ADMISSIBILITY_MVP.md` (MVP scope + acceptance)

---

## Finding #1 — `MUST_HAVE` operator vs. destructive-class missing-precondition (contradiction)

**Where.** `ACTION_GATE_SPECIFICATION.md §4` maps the generic hard-invariant
operator `MUST_HAVE <evidence>` to the outcome **`REQUEST_MORE_EVIDENCE`** when
the evidence is absent (the action is not rejected; the gate asks for the
missing artifact). Separately, `ACTION_GATE_SPECIFICATION.md §10` (transition
F3), `§11` (acceptance A4), and `AGENT_ACTION_ADMISSIBILITY_MVP.md §10` (T3)
state that a `DB_DELETE` (irreversible destructive class) **without a verified
restorable backup** must resolve to **`DENY`**.

**Contradiction.** For the specific case "`DB_DELETE` + missing
`verified_restorable_backup`", `§4` implies `REQUEST_MORE_EVIDENCE` while
`§10/§11`/MVP require `DENY`. Both cannot hold.

**Resolution (fail-closed, more restrictive wins).** The destructive-class
requirement is the more conservative and is stated in three independent places,
so it governs. The reference marks that single precondition as **hard** in the
policy rule and the evaluator treats a hard `MUST_HAVE` miss as `DENY`:

- `action_gate_ref/policy.py` — rule `R3` (`DB_DELETE`) carries
  `{"op": "MUST_HAVE", "evidence": "verified_restorable_backup", "hard": True}`.
- `action_gate_ref/gate.py` — the `MUST_HAVE` branch resolves a miss to `DENY`
  when `hard` is set, otherwise to `REQUEST_MORE_EVIDENCE` (the `§4` default).

**Blast radius.** Decision-layer only. No hashing, projection, approval, token,
or audit semantics are affected. A non-hard `MUST_HAVE` (e.g. `DEPLOY`'s
`signed_artifact`, `R2`) still follows the `§4` default of
`REQUEST_MORE_EVIDENCE`. Tests: `tests/test_acceptance.py::test_A4_missing_backup_denied`
(hard → DENY) and `tests/test_acceptance.py::test_A5_unavailable_simulation_retries`
(non-hard path unaffected).

**Recommended spec edit (out of scope to apply here).** In `§4`, annotate
`MUST_HAVE` with: "unless the operation class declares the precondition
*dispositive*, in which case a miss is `DENY`." Then `§10/§11` become consistent
special cases rather than contradictions.

---

## Finding #2 — `ALLOW_WITH_CONSTRAINTS` precedence vs. bare `ALLOW` (under-specification)

**Where.** `ACTION_GATE_SPECIFICATION.md §4` defines a precedence ordering over
the six outcomes ("most restrictive wins") but lists `ALLOW` and
`ALLOW_WITH_CONSTRAINTS` without stating their relative order. When a rule's only
permitting effect is `ALLOW_WITH_CONSTRAINTS`, an evaluator that treats the two
as equal severity can let a default `ALLOW` shadow the constrained variant and
**drop the constraints** — a silent loss of a safety obligation.

**Resolution.** `ALLOW_WITH_CONSTRAINTS` is defined as **strictly more
restrictive** than a bare `ALLOW`, so it wins the tie and always carries its
constraints into the decision (`action_gate_ref/gate.py`, `_SEVERITY`:
`ALLOW_WITH_CONSTRAINTS < ALLOW`). This is the only defensible reading of
"most restrictive wins."

**Blast radius.** Decision-layer only. Tests:
`tests/test_gate_transitions.py::test_constrained_allows_carry_constraints`
(SECRET_READ/MONITORING_DISABLE/DB_MUTATION/EXTERNAL_COMMS all retain
non-empty constraints).

**Recommended spec edit.** State in `§4`: "`ALLOW_WITH_CONSTRAINTS` ranks below
`ALLOW`; constraints are cumulative and never discarded."

---

## Finding #3 — Present-but-invalid approval: `DENY` vs `ESCALATE_TO_HUMAN` (under-specification)

**Where.** `§4`/`§11` distinguish an **absent** approver (→ `ESCALATE_TO_HUMAN`,
"go get a human") from a **present but invalid** approval, but do not name the
outcome for the latter (expired, wrong policy_hash, wrong action_hash, bad
signature, insufficient quorum, SoD violation).

**Resolution.** A submitted-but-invalid approval is treated as **`DENY`**
(fail-closed): a malformed or stale authorization is a rejection, not a prompt
for escalation, because the requester already attempted to supply authorization
and it did not validate. Absent approvals still escalate.
(`action_gate_ref/gate.py::_approver_satisfied` returns `(satisfied,
present_but_invalid)`; the evaluator maps `present_but_invalid → DENY`,
`absent → ESCALATE_TO_HUMAN`.)

**Blast radius.** Decision-layer only. Tests:
`test_A2_expired_approval_denied`, `test_A3_policy_mismatch_denied`,
`test_A9_approval_modification_denied`, `test_A10_action_modification_denied`.

**Recommended spec edit.** In `§11`, add a row: "approval present but fails any
binding check ⇒ `DENY`; approval absent ⇒ `ESCALATE_TO_HUMAN`."

---

## Finding #4 — `sha-512-256` availability is runtime-dependent (portability note)

**Where.** `ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §17` names `sha-256`
(default) and `sha-512/256` (alternative). `sha512_256` is present in CPython's
bundled OpenSSL on all supported reference platforms, but the spec does not say
what a conforming implementation must do if a runtime lacks it.

**Resolution.** The alternative is treated as **capability-gated, never
silently downgraded**: `hashing.algorithm_supported()` gates it, and pinned
`sha-512/256` digests are emitted only when the runtime supports it
(`conformance.pinned_digests`). `sha-256` is always required. Requesting an
unsupported algorithm raises `ValueError` (fail-closed), never falls back to a
weaker hash.

**Blast radius.** None to `sha-256` semantics. Note only.

**Recommended spec edit.** In `§17`, add: "`sha-256` is mandatory to implement;
`sha-512/256` is optional-to-offer but, if offered, must match the pinned
vectors; no implementation may substitute a different algorithm on absence."

---

## Non-findings (checked, no contradiction)

- **`action_id` / `timestamp` exclusion vs. replay.** Excluding them from
  `action_hash` (§10) does not weaken replay protection: replay is bound by
  nonce + `current_state_hash` (§13/§15), verified independently. Consistent.
- **Set path `credential_scope.permissions`.** Order-independence (§7) is
  compatible with "credential expansion changes the hash" (§10): adding a
  permission changes the *set*, hence the digest; only reordering is neutral.
  Vectors V8 and V12 both hold.
- **Bare-number prohibition vs. counts.** All counts/costs are typed strings
  (`affected_count`, `projected_cost`), so `MAX_SCOPE`/`MAX_COST` compare parsed
  integers without introducing bare JSON numbers into any hashed payload.
  Consistent.
