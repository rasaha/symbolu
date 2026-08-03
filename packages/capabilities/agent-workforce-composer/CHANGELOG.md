# Changelog

All notable changes to `ugence-agent-workforce-composer` are documented here.
This project versions the distribution independently of the Ugence platform.

## [0.1.0] — Agent Workforce Composer P1

First canonical distribution. Contract version `awc.v1`.

### Added
- **Canonical planning object model** (frozen, `extra='forbid'`, content-addressed):
  `WorkflowRoleRequirement`, `NonAgentDisposition`, `WorkflowNodeDisposition`,
  `AgentProfile`, `AgentCapability`, `AgentCapabilityEvidence`,
  `CapabilityEvidenceSet`, `AgentRegistrySnapshot`, `EnterpriseAgentPolicy`,
  `EligibilityPolicy`, `AgentEligibilityResult`, `RoleEligibilityReport`,
  `EligibilityExplanation`, `EligibilityReplayRecord`.
- **`CompilerWorkflowAdapter`** — read-only, data-only adapter over a serialized
  Policy Workflow Compiler `WorkflowIR` (`workflow_ir.v1`). Total node accounting;
  fail-closed on unknown version / missing digest / malformed graph; authority
  preservation for governance and human nodes.
- **Hard-constraint eligibility engine** — deterministic, fail-closed, complete
  elimination accounting; evidence discipline (DECLARED / MEASURED / OBSERVED with
  `OBSERVED > MEASURED > DECLARED` precedence); append-only `EliminationReason`
  taxonomy.
- **Deterministic explanation & replay**; content fingerprints on every object.
- **Frozen synthetic fixtures** — procurement / support / security workflows and a
  ~17-agent registry exercising every important elimination reason.
- **Offline CLI**, **frozen public-API artifact + drift verifier**, **isolated
  distribution verifier**, **tests**, **docs**, and **path-scoped CI**.

### Not implemented (by design; see `docs/NEXT_PHASES.md`)
Ranking, scoring, winner selection, team composition, permission assignment,
fallback selection, runtime handoff, H16 migration, Agent Runtime / H22 adapters,
Model Selection invocation, live registration, agent execution.
`pilot_validated=false`, `production_certified=false`.
