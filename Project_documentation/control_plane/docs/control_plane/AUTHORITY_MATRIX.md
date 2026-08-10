# Authority and Responsibility Matrix

*Phase 2. Exactly one authoritative owner per decision category. Overlaps are resolved by
assigning a single owner + advisory inputs — never by multiple authoritative owners.*

Columns: **Owner** (authoritative) · **Advisory** (may inform) · **Prohibited** (must not decide) ·
**Conflict rule** · **Fail** (open/closed) · **Evidence** · **Reason ns** · **Escalation**.

| Category | Owner | Advisory | Prohibited | Conflict rule | Fail | Evidence | Reason ns | Escalation |
|---|---|---|---|---|---|---|---|---|
| provider reachability | ExecutionGate | telemetry | ModelPolicy, Action* | live_probe > cache | closed | probe | `EXEC.*` | exclude+retry-source |
| authentication | ExecutionGate | — | all others | live_probe wins | closed | probe | `EXEC.*` | ops |
| billing | ExecutionGate | telemetry | ModelPolicy | probe > cache | closed(if require_billing) / indeterminate | probe | `EXEC.*` | ops |
| quota | ExecutionGate | telemetry | ModelPolicy | freshest | operational→conditional | probe | `EXEC.*` | backoff |
| regional eligibility | ExecutionGate | — | ModelPolicy | config authoritative | closed | policy_context | `EXEC.*` | policy owner |
| data residency | ExecutionGate (+PolicyContext source) | — | ModelPolicy, Provider | policy_context wins | **closed** | policy_context | `EXEC.*`/`POLICY.*` | compliance |
| provider approval | PolicyContext → ExecutionGate | — | ModelPolicy | enterprise policy wins | **closed** | policy_context | `POLICY.*` | compliance |
| model capability | ModelPolicy | registry (measured) | ExecutionGate | measured > declared | n/a (scoring) | registry | `MODEL.*` | — |
| quality threshold | ModelPolicy (hard gate) | telemetry | ExecutionGate, Action* | frozen threshold | closed (gate) | registry/telemetry | `MODEL.*` | abstain/human |
| cost objective | ModelPolicy | — | ExecutionGate(owns cost *ceiling*) | ceiling(EXEC) precedes objective(MODEL) | n/a | declared price | `MODEL.*` | — |
| latency objective | ModelPolicy | telemetry | ExecutionGate(owns latency *SLA*) | SLA(EXEC) precedes objective(MODEL) | n/a | telemetry | `MODEL.*` | — |
| assertion support | AssertionGovernance (TAP) | model output | ActionGate, ModelPolicy | evidence-grounded | closed (reject) | evidence set | `ASSERT.*` | human review |
| uncertainty disclosure | AssertionGovernance | — | ActionGate | qualify-or-reject | closed | evidence | `ASSERT.*` | human |
| prohibited claims | AssertionGovernance | policy_context | Provider, ModelPolicy | policy wins | **closed** | policy_context | `ASSERT.*`/`POLICY.*` | compliance |
| action authorization | ActionGate | assertion disposition | Assertion, ModelPolicy, Provider | deny > allow | **closed** | policy_context+state | `ACTION.*` | human approve |
| action scope | ActionGate | request envelope authority | Provider, adapter | envelope bounds ActionGate | **closed** | envelope | `ACTION.*` | human |
| approval requirement | ActionGate (from policy_context) | risk class | adapter | require-approval > auto | closed | policy_context | `ACTION.*` | human authority |
| execution adapter choice | Orchestrator (mechanism) | — | ExecutionGate, ModelPolicy, ActionGate | selected model/action binds adapter | n/a | selection/approval | `RUNTIME.*` | ops |
| fallback authorization | Orchestrator → re-enter ExecutionGate+ModelPolicy | — | Provider, adapter | fallback re-evaluates eligibility | closed | new decision | `RUNTIME.*` | ops |
| retry authorization | Orchestrator (typed: transient only) | telemetry | Provider silently | semantic-fail → different model | closed | outcome | `RUNTIME.*` | ops |
| audit ownership | Audit (append-only) | all components emit | any (rewrite) | append-only; hash chain | **closed** (block enforce on failure) | prior hash | `AUDIT.*` | ops/compliance |
| telemetry ownership | Telemetry | components emit | any (edit decisions) | prospective only | open (advisory) | observation | `AUDIT.*` | — |
| policy version | PolicyContext | — | mid-trace upgrade | pinned per trace | closed | envelope | `POLICY.*` | ops |
| registry version | Registry | telemetry (prospective) | mid-trace mutation on a running trace | pinned per trace | closed | manifest | `POLICY.*` | ops |

## Flagged overlaps and their resolution

- **cost / latency (EXEC vs MODEL):** EXEC owns the *hard ceiling/SLA* (eligibility); MODEL owns the
  *preference/objective* (ranking). Distinct owners, fixed precedence (ceiling first).
- **residency / provider approval:** sourced from `policy_context`, *enforced* by ExecutionGate as a
  critical fail-closed condition; ModelPolicy and adapters are prohibited deciders.
- **assertion vs action:** two separate owners (AssertionGovernance, ActionGate). Assertion approval is
  **advisory input** to ActionGate, never authorization. Kept independently governable (invariant 17).
- **fallback/retry:** owned by the Orchestrator as *mechanism*, but every fallback **re-enters**
  ExecutionGate + ModelPolicy (invariant 19); no component may silently pick a fallback.

## Rule

No category has two authoritative owners. Advisory components may inform but not decide. Prohibited
components must emit `POLICY_CONFLICT` (namespaced) rather than assume authority.
