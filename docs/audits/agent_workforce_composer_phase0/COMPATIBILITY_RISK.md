# Compatibility & Migration Risk

Migration is **not executed** in Phase 0. This file records the risk analysis that
justifies the ADR's compatibility strategy and the H16 dispositions. It
distinguishes identity-preserving compatibility, adapter-based compatibility, and
retained H16 runtime objects.

## Blast radius

`agentic/agentic_framework/coordination.py` is re-exported wholesale by the
package `__init__` (`:312`) and imported by 8 sibling modules, 6+ examples, and
`test_coordination.py`. `multi_agent.py` is re-exported at `__init__:219`. Because
the package surface re-exports every symbol, **any rename must preserve the
`agentic.agentic_framework` public names.** This is the dominant compatibility
constraint.

## Three compatibility treatments

### 1. Identity-preserving compatibility (only where semantics are identical)

Use a logic-free re-export of the canonical AWC object from the old H16 import
path. Candidate: **`AgentProfile`** — *iff* the canonicalized AWC profile has the
same fields and frozen semantics as `coordination.py:116`. If fields diverge
(e.g. AWC adds measured/observed capability tiers, provenance, or a registry
snapshot id), it drops to treatment #2.

```
# future H16 shim (illustrative, not implemented in P0)
from ugence_agent_workforce_composer.models import AgentProfile  # re-export
```

Risk: field drift silently breaks pickle/`to_dict` round-trips. Mitigation:
serialization-compatibility test comparing `to_dict()` output before/after.

### 2. Adapter-based compatibility (runtime-specific / mutable differ)

Use an explicit adapter where the runtime object has mutable state or fields the
planning object must not carry. Candidates: **`CapabilityRegistry`** (mutable
availability vs. immutable snapshot), **`DelegationContract`** (runtime grant vs.
planning `AgentAssignment`), **`AuthorityModel`** (runtime `authorize()` binding
budget/ownership vs. AWC pure hard-constraint eligibility).

```
AgentTeamPlan (AWC)  ──adapter──▶  DelegationContract / Coordinator inputs (H16)
```

The adapter must be **narrowing-only**: it may drop planning metadata but must
never broaden `authority_scope`, permissions, provider allowance, residency, tool
access, cost ceiling, or quality floor.

### 3. Retained H16 runtime objects (no migration)

Runtime-only objects stay in H16 unchanged: `Coordinator`, `AgentAssignment`
(mutable), `GoalOwnershipLedger`, `CoordinationTrace`/`Result`, all worker types,
and the entire `multi_agent.py` layer (`AgentRegistry`, routers,
`MultiAgentOrchestrator`) — including the nondeterministic `LLMRouter`, which must
never enter the deterministic AWC. Do not force these into AWC to reduce file
count.

## Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Name collisions (`AgentProfile`, `CapabilityRegistry`, `AgentAssignment`) resolved by merging semantically different types | High | Keep distinct namespaces; only `AgentProfile` is a re-export candidate, and only under a field-identity test. |
| R2 | AWC importing the coupled `agentic/` runtime tree (Option C) | High | ADR selects Option A; P1 import-boundary test forbids `agentic` imports from AWC. |
| R3 | Runtime silently reselecting an agent that broadens authority | High | Runtime fallback restricted to an AWC-approved fallback set or triggers governed reassessment. |
| R4 | `UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT` — compiler `WorkflowIR`/registry evolves and AWC misclassifies | Medium | Adapter pins `workflow_ir.v1` + known enum sets; unknown version/node fails closed; drift alarm. |
| R5 | Serialization drift breaking H16 consumers/tests | Medium | Preserve `to_dict()` shapes; add round-trip compatibility tests before any re-export. |
| R6 | Public-name breakage in `agentic.agentic_framework` | Medium | Preserve every re-exported name; platform-freeze API snapshot guards it. |
| R7 | Enum introduction (H16 uses string-constant classes) changing comparison/serialization sites | Low | If AWC introduces enums, keep string values equal to today's literals. |

## Migration order (future, not executed here)

1. Land AWC leaf package with canonical `AgentProfile` + `AgentRegistrySnapshot` +
   eligibility (P1), **without** touching H16.
2. Add adapters (`CompilerWorkflowAdapter`, `AgentTeamPlan → coordination`) (P1–P4).
3. Introduce H16 re-export/adapter shims behind serialization + import-boundary
   tests (P4).
4. Only then consider deprecating duplicated H16 selection concepts (`DEPRECATE_LATER`).

## Rollback & SemVer

- **Rollback:** shims are additive; removing them restores today's H16 exactly.
- **SemVer:** AWC is `0.x` (pre-1.0, unstable). H16 re-exports that preserve names
  and serialization are **minor/patch**; any field or name change to a re-exported
  H16 symbol is **major**. The platform-freeze API snapshot is the enforcement
  point.
