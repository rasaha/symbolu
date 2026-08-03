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

## Fingerprints (two, v0.1.1)

To avoid overloading one field with two meanings, a result carries two digests, each
a domain-separated SHA-256 over canonical JSON (sorted keys, no whitespace, no
`repr()`), and neither includes the opaque equivalence-key *value*:

- **`outcome_fingerprint`** — the *selected outcome* only: context id; mode; ordered
  surviving ids; sorted structurally-removed / extractively-removed / restored /
  protected id sets; equivalence status; fallback flag; policy **version**; oracle id;
  oracle contract version. It does **not** bind token counts, unit text, requested
  reduction/budget, evaluation time, reason codes, the policy fingerprint, or the
  oracle validity/correlation. Byte-identical to the v0.1.0 `fingerprint` field.
- **`run_fingerprint`** — the *complete run identity*: request identity (context
  contract version, id, correlation, ordered per-unit content digests + resolved
  token counts + protected flag + redundancy set, requested reduction, requested
  token budget, mode, evaluation time), policy identity (version + actual
  `policy.fingerprint()` + token-counter mode), oracle identity (id, contract version,
  evaluation ref, validity horizon, correlation), and the outcome including reason
  codes.

`fingerprint` is a **deprecated alias** of `outcome_fingerprint`. Changing the context
text, correlation, requested reduction, token budget, policy, or resolved token counts
changes `run_fingerprint`; changing what survived changes both. Dictionary/metadata
ordering never changes either digest.

**Strict canonical JSON (v0.1.2).** All fingerprint/policy serialization uses
`allow_nan=False`, so a digest can never contain the non-standard `NaN` / `Infinity`
tokens — a non-finite number raises `ValueError` deterministically instead of yielding
an unstable digest. Timestamps and token counts are validated to be finite before they
can reach a digest.

**Token-counter identity (v0.1.2, `run/2`).** The run fingerprint identifies an injected
token counter by an explicit optional `counter_id` (with optional `counter_version`),
falling back to the fully-qualified type name (`module.qualname`) — not the bare class
name, which two different counters could share. The default counter is `"default"`.
