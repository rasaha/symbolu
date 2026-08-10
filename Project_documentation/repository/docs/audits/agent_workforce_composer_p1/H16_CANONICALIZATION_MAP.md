# H16 Canonicalization Map (P1 realization)

Phase 0 ADR selected **Option A**: canonicalize deterministic agent selection into
AWC; H16 retains runtime coordination, dispatch, recovery, live availability,
runtime fallback and `LLMRouter`. **P1 does not modify H16 source
(`coordination.py`, `multi_agent.py`), does not move any H16 class, and adds no H16
compatibility facade** (deferred to P4).

| Phase 0 disposition | H16 symbols | P1 realization in this package |
|---|---|---|
| CANONICALIZE_INTO_AWC | `AgentProfile` | `agents.AgentProfile` — distinct, evidence-backed, content-addressed type (not a re-export) |
| ADAPT_TO_AWC | `CoordinationGoal` | `workflow.WorkflowRoleRequirement` derived from `WorkflowIR` |
| ADAPT_TO_AWC | `CapabilityRegistry` | split into `AgentRegistrySnapshot` (data) + `eligibility` engine |
| ADAPT_TO_AWC | `AuthorityModel` | hard-constraint eligibility only; runtime `authorize()` stays in H16 |
| ADAPT_TO_AWC | `DelegationContract` | **deferred** — planning assignment is P2; runtime contract stays in H16 |
| REFERENCE_ONLY | `RejectionReason`, `Mission`, `AuthorityDecision` | not imported; informed the `EliminationReason` taxonomy design |
| REMAIN_IN_H16 | `Coordinator`, runtime `AgentAssignment`, `LLMRouter`, `MultiAgentOrchestrator`, … | untouched |
| COMPATIBILITY_FACADE_CANDIDATE | `AgentProfile` re-export | **deferred** (see field diff below) |

## `AgentProfile` field diff (decides re-export vs adapter)
H16 runtime (`coordination.py:116`): `agent_id, role, capabilities:FrozenSet[str],
permissions:FrozenSet[str], owned_tools:FrozenSet[str], supported_goals:FrozenSet[str],
execution_limits, trust_level:int`.

AWC adds: `agent_version`, `provider_id`, `status`, declared/measured/observed
capability claims + `AgentCapabilityEvidence`, validity window, `provenance`,
`profile_fingerprint`. **Field sets diverge → identity re-export not viable;** the
facade candidate is deferred. See `packages/.../docs/H16_CANONICALIZATION_STATUS.md`.
