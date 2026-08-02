# Determinism

Identical input + policy + oracle evaluations ⇒ identical output ids and identical
result fingerprint.

## Selection policy — safety vs. optimization

`MinimizationPolicy` governs only the **order** in which already-eligible
(unprotected, non-duplicate) units are considered for extractive removal:

- **Optimization (policy):** source-type priority, filler hints, larger-span-first,
  id tie-break. All deterministic; the removal key is a total order.
- **Safety (not policy):** protected mask, oracle equivalence, restoration, fallback.
  These are never influenced by the policy.

The policy is versioned (`version`) and fingerprinted (`fingerprint()`), so a change
is visible in every result's `policy_version` and in the result fingerprint.

## Token accounting

The core requires no particular tokenizer or model. Token counts resolve in order:

1. per-unit caller-supplied `token_count`,
2. an injected `TokenCounter`,
3. the neutral `default_token_count` (a transparent word/punct regex approximation).

Defined behaviour: missing counts → default counter; zero-token spans → 0; negative
`token_count` → `ValueError` at construction; `target_reduction` outside `[0, 1]` →
`InvalidRequestError`; negative `token_budget` → `InvalidRequestError`; an impossible
budget → the safest achievable result plus `BUDGET_UNREACHABLE_WITHOUT_PROTECTED`.

Because the default counter is approximate, **do not** present reductions computed from
it as exact provider billing savings.

## Fingerprint

`result_fingerprint(...)` is a domain-separated SHA-256 over canonical JSON of the
outcome (ordered surviving ids; sorted removed/restored/protected id sets;
equivalence status; fallback flag; policy version; oracle identity). It deliberately
excludes the opaque equivalence-key *value* (the oracle's private contract). Changing
the context id, the policy, or the outcome changes the fingerprint.
