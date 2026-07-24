# Integration-Failure Taxonomy (Phase 16) & Fault-Injection Results (Phase 17)

*Thirty ways component composition can fail, and the fault-injection study that exercises them.
`governed_inference_pilot/fault_injection.py`. The invariant under test: every fault must leave the
runtime **fail-closed, diagnosable, and auditable** — never a silent permissive fallback.*

## The thirty integration failures

| # | Failure | Mechanism | Sev | Detect | Expected pipeline response |
|---|---|---|---|---|---|
| 1 | schema mismatch | payload shape wrong | high | contract | CONTRACT_ERROR (fail closed) |
| 2 | vocabulary mismatch | unknown disposition value | crit | contract | INDETERMINATE, never ALLOW |
| 3 | policy-version mismatch | stale policy version | high | version check | ESCALATE / CONTRACT_ERROR |
| 4 | missing required field | absent contract field | high | contract | CONTRACT_ERROR |
| 5 | unknown disposition | out-of-vocab downstream state | crit | reconciliation | INDETERMINATE |
| 6 | adapter semantic loss | governing field dropped in transform | crit | semantic-loss check | fail closed |
| 7 | claim-reference loss | claim id lost | high | audit refs | INDETERMINATE |
| 8 | citation-reference loss | citation detached | high | binder | binder error code |
| 9 | evidence-link drift | evidence bound to wrong claim | high | binder | binder error |
| 10 | risk-tier mismatch | wrong config for risk | high | policy | escalate |
| 11 | assertion/action authority confusion | action allowed via assertion allow | crit | precedence | action block outranks |
| 12 | execution/model identity mismatch | fixture ≠ selected | med | fixture record | flagged |
| 13 | stale registry | eligibility stale | high | exec gate | INELIGIBLE |
| 14 | fallback without audit | silent fallback | crit | audit completeness | fail closed |
| 15 | error swallowed downstream | exception → success | crit | safe() wrapper | INDETERMINATE + STAGE_EXCEPTION |
| 16 | double abstention | two stages abstain | med | reconciliation | INDETERMINATE |
| 17 | qualification → allow | qualify silently upgraded | crit | precedence | qualify never > reject |
| 18 | reject → escalation | reject downgraded | med | precedence | both are withholds |
| 19 | action block hidden by assertion allow | allow masks block | crit | precedence | BLOCK outranks ALLOW |
| 20 | stage skipped without authority | silent skip | crit | orchestration rules | explicit-only skipping |
| 21 | missing provenance after transform | provenance dropped | high | binder | MISSING_PROVENANCE |
| 22 | trace linkage break | orphan event | high | audit | incomplete audit flagged |
| 23 | replay nondeterminism | signature varies | crit | replay | detected as drift |
| 24 | latency timeout altering policy | budget → downgrade | crit | budget check | INDETERMINATE (fail closed) |
| 25 | cost fallback altering risk posture | budget → downgrade | crit | budget check | INDETERMINATE |
| 26 | human override without reason | silent override | crit | audit | disallowed (no silent override) |
| 27 | component exception treated as success | swallow | crit | safe() | INDETERMINATE |
| 28 | unsupported default value | bad default | med | contract | flagged |
| 29 | inconsistent jurisdiction | juris drift | med | request | flagged |
| 30 | cross-tenant artifact reference | tenant leak | crit | request | fail closed |

## Fault-injection results (clean cases, where a naive pipeline would ALLOW)

21 faults injected into the clean partitions (the cases that legitimately allow — the hardest place to
stay fail-closed under a fault). Result:

- **0 unsafe fallbacks across all 21 faults** — no injected fault produced `WOULD_ALLOW`.
- **fail-closed rate 1.00** on every decision-path fault (missing field, malformed disposition, stale
  registry, unavailable model, contract/policy mismatch, claim/assertion/action exceptions, evidence
  indeterminate, scope ambiguity, conflicting stage decisions, corrupted references, budget exhaustion,
  audit-write failure).
- **auditable rate 1.00** — every fault produced a complete audit trace.
- **Integrity faults** (replay-hash-mismatch, duplicated-trace-identifier) are scored by **replay
  detection**, not by the live decision: both are detected as non-deterministic drift at replay (a
  clean case legitimately allows; the integrity violation is caught at the replay/audit layer, which is
  where it belongs).

## Two honest corrections made during the study

1. **Budget exhaustion originally did not affect the decision**, so on clean cases it wrongly read as
   "unsafe fallback." Corrected: the orchestrator now fails closed to `INDETERMINATE` when a latency or
   cost budget is exhausted — governance is never silently downgraded to meet a budget.
2. **Audit-write failure** likewise now fails closed to `PIPELINE_ERROR` — no governance decision may
   stand without a durable audit trail. (Both are decision-path invariants, not just instrumentation.)

The taxonomy row for each fault names its expected response; the fault-injection sweep confirms the
runtime meets it.
