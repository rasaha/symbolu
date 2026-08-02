# Protection contract (v1)

## The rule

> **A unit marked protected is never removed by any minimization stage** — structural
> dedup, redundancy-set collapse, extractive selection, restoration, or fallback.

Uncertainty retains: a `ProtectionProvider` that is unsure marks a unit
`uncertain`, and uncertain units are treated as protected (retained).

## v1 choice: protected identity means "this exact unit must remain"

There are two possible readings of a protected duplicate:

- *the information must remain represented* (a protected duplicate could be dropped if
  a copy survives), or
- *this exact unit must remain*.

**v1 chooses the latter (safer) contract:** every protected unit id remains; structural
deduplication applies only to *unprotected* units; two protected duplicates are **both**
retained. A future version may add an explicit `protected_equivalence_group` contract if
"represented, not identical" is required.

This is a deliberate hardening over the experimental prototype, whose
`structural_compress` accepted `protected_ids` but ignored them (a protected duplicate
could be removed because another copy remained).

## Sources of protection

The effective protected set is the union of:

1. `protected_ids=[...]` passed to the call,
2. units constructed with `protected=True`,
3. a supplied `ProtectionResult` (or a `ProtectionProvider.protect(context)` result)'s
   `effective_protected` (= `protected_ids ∪ uncertain_ids`).

## Ranking cannot override protection

Optional ranking signals (source-type priority, filler hints, span size) only reorder
units *already eligible* for removal. They can never remove protection, bypass the
oracle, change the equivalence requirement, or turn a failed check into success.

## Tests

`tests/protection/test_protection.py` covers: protected unit never selected; uncertain
retained; ranking cannot override protection; provider failure fails closed; malformed
provider result fails closed; duplicate protected units both retained (v1 contract);
and a directly-supplied `ProtectionResult`.
