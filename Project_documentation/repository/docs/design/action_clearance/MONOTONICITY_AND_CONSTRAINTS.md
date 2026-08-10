# Monotonicity & Constraint Intersection

## The invariant, formally

> **Clearance permissions ⊆ ActionGate-authorized permissions.**

The set of what a `ClearanceResult` permits is always a (non-strict) subset of what the underlying
`ActionGovernanceResult` authorized. Clearance is a **narrowing** operation composed with the identity;
it has no widening operation in its algebra.

## Forbidden widenings (exhaustive)

Action Clearance must never:

1. add an action,
2. add a target,
3. expand parameters,
4. extend authorization expiry,
5. remove an upstream obligation,
6. replace the authorized actor,
7. change the authorized artifact,
8. substitute a different execution method,
9. convert an ActionGate denial into an executable result.

Each maps to a security invariant in [`SECURITY_INVARIANTS.md`](SECURITY_INVARIANTS.md) and a
fail-closed acceptance scenario in [`ACCEPTANCE_SCENARIOS.md`](ACCEPTANCE_SCENARIOS.md).

## Deterministic constraint intersection

Let `A` = the authorization's constraint set (from `ActionGovernanceResult.constraints`) and `C` = the
clearance-policy's additional constraint set. The evaluator computes:

### Compatible constraints (narrowing)

```text
effective_constraints = A ∩ C          # only restrictions common-or-added; clearance may only tighten
```

Interpretation: a clearance constraint may **add** a restriction (e.g. "only during business hours") or
**re-assert** an authorization constraint. It may never drop an authorization constraint. The result's
`effective_constraints` therefore always **contains every element of `A`** and may add elements from
`C`; equivalently, the *permitted* space is `A`-permitted **minus** `C`-restricted — a subset of
`A`-permitted. (The set intersection is over the *restriction* representation; the permission space it
induces is a subset. See the worked example.)

### Direct conflict

A clearance constraint that would **relax** an authorization constraint, or two constraints that cannot
both hold, is a direct conflict:

```text
CONSTRAINT_CONFLICT → BLOCK or ESCALATE          # default ESCALATE
```

Default is `ESCALATE` (a human resolves the conflict); policy may configure `BLOCK` for classes known
to be unrecoverable. The conflict is **never** resolved by dropping the authorization constraint.

### Missing interpretation rule

If the evaluator has no deterministic rule for combining two constraints (unknown comparator, unknown
constraint kind, un-orderable domains):

```text
fail closed → CLEARANCE_POLICY_CONFLICT → ESCALATE
```

Never silently union, and never guess a merge.

## Worked example

```text
Authorization A: { merge_window ⊆ 09:00–18:00 UTC, required_reviews ≥ 2 }
Clearance    C: { merge_window ⊆ 10:00–12:00 UTC }
effective    = { merge_window ⊆ 10:00–12:00 UTC, required_reviews ≥ 2 }   # tighter window; reviews kept
```

Permitted merge times went from a 9-hour span to a 2-hour span — a strict subset — and no
authorization constraint was dropped. Monotonicity holds.

```text
Authorization A: { required_reviews ≥ 2 }
Clearance    C: { required_reviews ≥ 1 }          # would RELAX
→ CONSTRAINT_CONFLICT → ESCALATE                  # never lowered to ≥ 1
```

## Obligations

Clearance may **add** obligations (e.g. "post a clearance audit entry") but may never **remove** an
upstream obligation. `effective_obligations ⊇ authorization_obligations`.
