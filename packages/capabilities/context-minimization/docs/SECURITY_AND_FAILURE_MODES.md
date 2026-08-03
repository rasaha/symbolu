# Security & failure modes

## Fail-closed by construction

Uncertainty always increases *retained* context; it never increases removal. There is
no "best-effort compressed" result on an oracle failure — an oracle failure returns the
**full context**.

| Condition | Behaviour | Reason code |
| --- | --- | --- |
| No oracle (oracle mode) | raise `OracleRequiredError` | — |
| Oracle raises | full fallback | `ORACLE_RAISED` |
| Non-string key / malformed result / empty oracle identity | full fallback | `ORACLE_RESULT_MALFORMED` |
| `oracle_id`/`contract_version` drift between calls | full fallback | `ORACLE_CONTRACT_MISMATCH` |
| `evaluation_time >= valid_until` (**inclusive**) | full fallback | `ORACLE_EVALUATION_EXPIRED` |
| `valid_until` supplied but no `evaluation_time` | full fallback | `ORACLE_EVALUATION_TIME_REQUIRED` |
| Context has correlation but evaluation omits it | full fallback | `ORACLE_CORRELATION_MISSING` |
| Context correlation ≠ evaluation correlation | full fallback | `ORACLE_CORRELATION_MISMATCH` |
| Changed equivalence key | restore necessary spans, else full fallback | `SPANS_RESTORED` / `JOINT_EFFECT_FALLBACK` |
| Joint effect unresolved by individual restoration | full fallback | `JOINT_EFFECT_FALLBACK` |
| Protection provider raises / returns garbage | protect everything (nothing removed) | `PROTECTION_PROVIDER_FAILED` |
| Impossible token budget | safest achievable result, flagged | `BUDGET_UNREACHABLE_WITHOUT_PROTECTED` |
| Invalid unit identity / duplicate ids | `ValueError` at model construction | — |
| Invalid target / negative budget | `InvalidRequestError` | — |

No invariant-check failure is silently continued past.

## No credentials, no I/O, no side effects

The core performs no network, disk, thread, scheduler, or credential access. Importing
it has no side effects and does not manipulate `sys.path`
(`tests/packaging/test_public_api.py::test_import_has_no_side_effects`).

## Immutability

Identity-bearing models are frozen dataclasses. Caller-supplied mappings are defensively
copied into read-only mappings, so a caller mutation cannot reach into a stored model,
and a stored model cannot be mutated to change a fingerprint after the fact.

## Trust boundary

The oracle is trusted to return a deterministic, canonical, non-sensitive key. The core
treats the key as opaque and never logs, parses, or forwards it. `equivalence_key`
values are excluded from the result fingerprint.
