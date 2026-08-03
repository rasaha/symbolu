# Invariance contract

## The oracle owns equivalence; the core compares an opaque key

```python
class InvarianceOracle(Protocol):
    def evaluate(self, context, *, evaluation_time=None) -> OracleEvaluation: ...
```

`OracleEvaluation` carries only what the minimizer needs:

| field | meaning |
| --- | --- |
| `equivalence_key` | **opaque** deterministic string; two contexts are equivalent iff equal |
| `oracle_id` | identifies the oracle (must be stable across the base/reduced calls) |
| `contract_version` | the oracle's contract version (must be stable across calls) |
| `evaluation_ref` | optional evaluation reference |
| `correlation_id` | optional; must match the context's correlation id if both are set |
| `valid_until` | optional epoch-seconds validity horizon |
| `reason_codes` | optional oracle-supplied codes (non-authoritative to the core) |
| `metadata` | optional non-sensitive string→string metadata |

**"Invariance" is relative to the supplied oracle.** The package creates no
authorization and never interprets the key's contents, never parses ActionGate
decision structures, and never constructs authorization semantics of its own. If you
supply an oracle that keys on nothing meaningful, the package will faithfully preserve
nothing meaningful — the guarantee is exactly as strong as your oracle.

## Why an opaque, oracle-owned key (not a `repr()` signature)

The experimental prototype built a decision-invariance signature *inside* the
compressor from `repr()` of ActionGate envelope/decision fields. That is unstable
(dict/`repr` ordering, non-versioned) and couples the reducer to ActionGate internals.
The canonical design moves semantic evaluation into the oracle, which returns a
**canonical, versioned, opaque key**. The reducer's only job is equality.

If an integration oracle generates the key, it MUST use canonical serialization,
deterministic ordering, an explicit contract version, domain-separated fingerprinting,
no credentials, no unstable `repr()`, documented included/excluded fields, and tests
proving materially different authorization results yield different keys. The core does
not broaden the equivalence definition.

## Correlation binding (mandatory, v0.1.1)

Correlation is part of the oracle-evaluation binding, not optional metadata. When the
input context carries a **non-empty** `correlation_id`, every usable evaluation —
baseline, reduced, each per-unit restoration eval, and the final restored eval — MUST
carry the identical id:

| context correlation | oracle correlation | outcome |
| --- | --- | --- |
| present | identical | usable |
| present | missing | fail closed — `ORACLE_CORRELATION_MISSING` |
| present | different | fail closed — `ORACLE_CORRELATION_MISMATCH` |
| absent | (any) | no binding required |

Missing and mismatched are **not** collapsed into one ambiguous code.

## Expiry (inclusive, deterministic, v0.1.1)

A validity horizon is **inclusive**: an evaluation is expired when
`evaluation_time >= valid_until`. The core never reads a wall clock — the caller
controls `evaluation_time` for deterministic replay. If `valid_until` is supplied but
`evaluation_time` is `None`, the run fails closed (`ORACLE_EVALUATION_TIME_REQUIRED`)
rather than assuming the evaluation is unexpired.

## Fail-closed conditions

Missing oracle → `OracleRequiredError` (raised, oracle mode only). Oracle raises →
`ORACLE_RAISED`. Non-string key or empty oracle identity → `ORACLE_RESULT_MALFORMED`.
`oracle_id`/`contract_version` drift → `ORACLE_CONTRACT_MISMATCH`.
`evaluation_time >= valid_until` → `ORACLE_EVALUATION_EXPIRED`; `valid_until` without
`evaluation_time` → `ORACLE_EVALUATION_TIME_REQUIRED`. Correlation missing →
`ORACLE_CORRELATION_MISSING`; correlation mismatch → `ORACLE_CORRELATION_MISMATCH`.
Changed key → restore or `JOINT_EFFECT_FALLBACK`. All resolve toward **more retained
context**.

The machine-readable version of this contract is `artifacts/invariance_contract.json`.
