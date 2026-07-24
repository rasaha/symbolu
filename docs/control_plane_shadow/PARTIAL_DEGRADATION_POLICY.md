# Partial Degradation Policy

*Phase 13. Behavior when a component is unavailable. Default rules (task): unknown critical
governance state must not become approval; assertion-only low-risk requests may degrade
differently from action-producing high-risk requests; action-producing requests fail closed when
ActionGate is unavailable; enforcement requiring audit halts if audit persistence fails.*

| Component down | May continue? | Allowed classes | Prohibited classes | Fallback | Fail | Audit req | Escalation |
|---|---|---|---|---|---|---|---|
| **ExecutionGate** | no | none | all | none — cannot establish eligibility | closed | record refusal | to operator |
| **ModelPolicy** | no | none | all | none — no selection without policy | closed | record refusal | to operator |
| **Provider adapter** | partial | assertion-only if cached output exists | any needing fresh generation | replay/next candidate (invariant 19) | closed | required | on repeated failure |
| **TAP (assertion)** | conditional | none that assert | any producing an assertion | none — cannot govern claims | **closed** (`GOVERNANCE_UNAVAILABLE`) | required | to human |
| **ActionGate** | conditional | assertion-only | **all action-producing** | none — cannot authorize | **closed** (`GOVERNANCE_UNAVAILABLE`) | required | to human |
| **Telemetry** | **yes** | all | none | skip prospective update | **open** (non-critical) | best-effort | none |
| **Audit** | no (where traceability required) | none | all | none | **closed** (`AUDIT_FAILURE`) | halt | to operator |
| **Policy registry** | no | none | all | none — versions unresolved | closed | record refusal | to operator |
| **Model registry** | no | none | all | none — no candidates | closed | record refusal | to operator |
| **Human-approval service** | conditional | auto-allowable actions only | any requiring approval | queue + wait | closed for approval-required | required | is the escalation |

## Verified against traces

- **TAP down** (T18) ⇒ `GOVERNANCE_UNAVAILABLE`, fail-closed, before any assertion is emitted.
- **ActionGate down** (T19, real action op) ⇒ `GOVERNANCE_UNAVAILABLE`, action-producing request
  refused; an assertion-only request under the same outage would still deliver (asymmetric
  degradation, as required).
- **Telemetry down** (T20) ⇒ assertion still delivered (`ASSERTION_DELIVERED`); telemetry is
  non-critical and fails *open* (the only fail-open component).
- **Audit down** (T21) ⇒ `AUDIT_FAILURE`; where traceability is required the trace cannot
  complete cleanly (invariant 15). In this pilot no enforcement occurs, so the "halt" is a
  terminal refusal, not a blocked real action.

## Key asymmetries

1. **Telemetry is the only fail-open component.** Everything else fails closed. This is
   deliberate: telemetry improves *future* routing and never gates a *current* decision, so its
   absence cannot make the system unsafe — only less informed.
2. **Governance-down is refusal, not degradation-to-allow.** TAP or ActionGate unavailable never
   yields an ALLOW/approval; unknown critical governance state ⇒ fail-closed
   (`RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE`). This directly answers Phase-16 falsification #14
   ("can the architecture degrade safely when a governance component is unavailable?"): yes — by
   refusing.
3. **Risk-tiered degradation.** An assertion-only informational request tolerates telemetry loss;
   an action-producing high-risk request tolerates nothing on its governance path.
