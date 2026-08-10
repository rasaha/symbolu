# ActionGate Interface Hardening

*Phase 7. Minimum stable action-governance interface, and the sharp distinctions the boundary
must preserve. Unlike TAP, the ActionGate boundary is a **clean semantic match**: the real
`action_gate_ref.gate.evaluate` is a genuine action-governance decision engine.*

## Minimum stable interface

**Input (action-governance request):**
- proposed action (operation + target + arguments + reversibility)
- governed assertion context (the governed output + provenance — per the TAP preregistration)
- request authority envelope (permitted actions, scope)
- human policy source (signed policy bundle — the rule source of truth)
- action risk class
- action scope
- target system
- approval requirements
- safety constraints
- provenance
- policy version

**Output (action-governance decision):**
- `action_disposition` ∈ {ALLOW, DENY, APPROVE, CONSTRAIN, ESCALATE, INDETERMINATE}
- constraints
- required approver
- approved scope
- denial reason
- escalation reason
- indeterminate reason
- hard safety block (flag)
- audit metadata (`action_hash`, `policy_hash`, dispositive rules)

## Can the current ActionGate artifact produce this directly?

**Yes.** `action_gate_ref.gate.evaluate(envelope, signed_policy, *, evidence, approvals, now)`
returns `outcome` (six values), `applied_constraints`, `dispositive_rules`, `action_hash`,
`policy_hash`, `state_trace`, `terminal`, `reason` — a superset of the required output. The
adapter maps the six outcomes to the canonical vocabulary (`vocabulary.ACTION_MAP`, low loss)
and derives the hard-safety-block flag from `terminal=DENIED` + `reversibility=IRREVERSIBLE`.

## Required distinctions (all preserved)

| Concern | Where it lives | Rule |
|---|---|---|
| **Human-rule source of truth** | signed policy bundle (`signed_policy`, `policy_hash`) | authoritative; tamper-evident |
| **LLM-derived policy interpretation** | **not used** in the reference gate | the gate is pure rules; no LLM interprets policy here |
| **Hard safety block** | `MUST_HAVE`-unmet on irreversible ⇒ DENY terminal | cannot be overridden by approval |
| **Approval workflow** | `ESCALATE_TO_HUMAN` + `approver_policy` ⇒ canonical APPROVE | requires attributable approver |
| **Action execution** | `ActionRuntimeAdapter` — **simulate only** | never executes; ENFORCEMENT disabled |

The reference gate uses **no LLM** to interpret policy — a strength: the human-rule source of
truth is not diluted by model interpretation. Any future LLM-derived interpretation must be
advisory only and never become the authoritative disposition.

## Gate before the adapter (invariant)

**No action reaches the action runtime adapter unless the disposition permits it AND all
constraints are satisfied.** Concretely, the orchestrator forwards to `ActionRuntimeAdapter`
only on canonical `ALLOW` with satisfied constraints; `DENY`, `APPROVE`, `ESCALATE`,
`CONSTRAIN` (unsatisfied), and `INDETERMINATE` are all terminal-before-execution. And even on
ALLOW, the runtime adapter simulates only (no real action in this pilot).

## Authority-envelope containment

ActionGate cannot authorize an action outside the request authority envelope (invariant 6). The
proposed action's operation/scope must be within the envelope's permitted set before the gate is
consulted; the gate then applies the signed policy on top. Both checks must pass.

## Avoided paths (real side effects)

The adapter wraps **only** `action_gate_ref` (pure). It never routes through
`action_gateway_k8s` (real kube-apiserver apply/delete), `action_gateway_isolated`
(real `broker.execute`), the MCP server, or `Gateway.execute_action`. These carry real-action
risk and are out of scope.
