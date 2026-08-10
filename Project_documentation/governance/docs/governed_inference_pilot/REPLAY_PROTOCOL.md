# Replay Protocol (Phase 6)

*`governed_inference_pilot/replay.py`. Deterministic replay compares a stored audit trace against a
re-run (or another trace) and detects drift. It **never calls live models** — replay operates only on
stored fixtures and traces.*

## Modes

| Mode | Question |
|---|---|
| `exact` | does the re-run reproduce the replay signature byte-for-byte? |
| `policy` | with the original stage evidence, do dispositions still match (ignoring input snapshot)? |
| `adapter_version` | do two traces from different adapter versions agree on decisions? |
| `component_version` | do two traces from different component versions agree? |
| `disposition_only` | do the final + per-stage dispositions match (ignore reason-code detail)? |
| `failure_injection` | after a fault, does the pipeline stay fail-closed (no permissive outcome)? |

## Drift detected

`input_drift`, `policy_drift`, `component_drift`, `hash_mismatch`, `missing_stage:<stage>`,
`disposition_drift:<stage>`, `reason_code_drift:<stage>`, `signature_mismatch`,
`unsafe_fallback_under_fault`. `deterministic` is false whenever a signature, disposition, or input
drift is present.

## Determinism guarantees

- Replay signatures cover **decision-bearing content only** (dispositions, reason codes, semantic
  loss), so latency/cost variation never registers as nondeterminism.
- `self_replay(trace)` is a sanity gate: a trace replayed against itself must be perfectly
  deterministic. The test suite (Phase 25) asserts this on every corpus trace.
- No `now()` / `random()` anywhere in the runtime, so exact replay holds across machines.

## Version comparison

`adapter_version` and `component_version` modes intentionally do **not** flag version differences as
drift (that is the axis under study); they flag **decision** differences *given* the version change —
answering "did upgrading this component/adapter change any governance decision, and where?" The
`detail` map records the exact stage and both dispositions for every changed decision.

## Failure-injection replay

In `failure_injection` mode the candidate trace was produced with a fault (Phase 17). The invariant:
the final shadow disposition must not be `WOULD_ALLOW`. Any permissive outcome under a fault is
`unsafe_fallback_under_fault` — a safety violation the fault-injection study (Phase 17) is built to
surface.
