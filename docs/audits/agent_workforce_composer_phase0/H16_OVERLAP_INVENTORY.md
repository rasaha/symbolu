# H16 Overlap Inventory

Full symbol inventory of the H16 coordination layer
(`agentic/agentic_framework/coordination.py`, `agentic/agentic_framework/multi_agent.py`)
with a reconciliation disposition for each symbol. The machine-readable form is
`H16_OVERLAP_INVENTORY.json`.

**Method.** Every class/dataclass/function in both modules was read at the merge
commit of PR #1305 (`0fa80fe4…`) and classified against the taxonomy in the
Phase 0 ADR. Identically named objects are **not** assumed semantically identical.

## Structural facts

- All 12 expected symbols exist with the exact requested names (none missing/renamed).
- **No enum types** — `CoordinationState`, `RejectionReason`, `MissionStatus` are
  string-constant classes; `decision`/`stop_reason` are bare `str`.
- **Serialization is hand-rolled** `to_dict()`/`to_list()`; no pydantic.
- `AgentProfile`, `CoordinationGoal`, `Mission`, `DelegationContract` are
  `@dataclass(frozen=True)`; lifecycle/result types are mutable.
- **`AuthorityModel` (`coordination.py:378`) is the sole authority decision-maker.**
  `CapabilityRegistry.candidates_for` and `GoalOwnershipLedger.is_owned_by_worker`
  are pre-filters; `DelegationContract`/`AgentProfile`/`CoordinationGoal` only carry
  authority data. `multi_agent.py` has **no authority model at all** (budget +
  handoff-count bounds only).

## Name collisions (highest-risk reconciliation items)

| Name | H16 (live) | Elsewhere | Reconciliation |
|---|---|---|---|
| `AgentProfile` | `coordination.py:116` frozen dataclass (worker authority envelope) | AWC docs propose a selection `AgentProfile` | Canonicalize the selection profile into AWC namespace; H16 gets a compat re-export **only if fields stay identical**, else an adapter. |
| `CapabilityRegistry` | `coordination.py:144` mutable registry + availability | Compiler `CapabilityRegistry` (`capability_registry.py:145`) — unrelated | AWC owns an immutable `AgentRegistrySnapshot`; H16 keeps its mutable runtime registry; compiler registry is a third, distinct type. Distinct namespaces. |
| `AgentAssignment` | `coordination.py:300` mutable runtime lifecycle object | AWC docs propose an immutable planning `AgentAssignment` | Keep both, in distinct namespaces. Do **not** merge; H16's is runtime/mutable, AWC's is planning/immutable. |
| `assigned_agent` / `authority_scope` | fields on `DelegationContract`/`CoordinationGoal` | H22 `PortfolioWorkflowEntry` fields; AWC-produced fields | These are the explicit cross-capability boundary fields (AWC produces → H22/H16 consume). Preserve names; never broaden `authority_scope` downstream. |

## Disposition summary

| Disposition | Symbols |
|---|---|
| **CANONICALIZE_INTO_AWC** | `AgentProfile` (as the canonical selection profile) |
| **ADAPT_TO_AWC** | `CapabilityRegistry` (snapshot+eligibility split), `CoordinationGoal` (→ `WorkflowRoleRequirement` derived from `WorkflowIR`), `DelegationContract` (planning `AgentAssignment` → runtime contract), `AuthorityModel` (hard-constraint eligibility → AWC; runtime `authorize()` → H16) |
| **COMPATIBILITY_FACADE_CANDIDATE** | `AgentProfile` (identity-preserving re-export iff fields unchanged) |
| **REFERENCE_ONLY** | `RejectionReason`, `Mission`, `AuthorityDecision`, `CoordinationTraceEntry` (concepts AWC mirrors with its own types) |
| **REMAIN_IN_H16** | `CoordinationState`, `MissionStatus`, `AssignmentTransition`, `AgentAssignment` (runtime), `OwnershipTransfer`, `GoalOwnershipLedger`, `WorkerResult`, `WorkerUnavailable`, `WorkerExecutor`, `AgentWorker`, `CoordinationTrace`, `CoordinationResult`, `Coordinator`, `format_coordination_trace`, `RegisteredAgent`, `AgentRegistry`, `AgentTurn`, `Handoff`, `MultiAgentResult`, `RouteDecision`, `Router`, `KeywordRouter`, `LLMRouter`, `MultiAgentOrchestrator` |
| **OUT_OF_SCOPE** | `ScriptedWorker` (test scaffolding) |
| **DEPRECATE_LATER** | (none at Phase 0) |

## Per-symbol table (abridged; full detail in the JSON)

| Symbol | Module:line | Phase | Det.? | Authority | Disposition |
|---|---|---|---|---|---|
| AgentProfile | coord:116 | selection | yes | carries | **CANONICALIZE_INTO_AWC** |
| CapabilityRegistry | coord:144 | mixed | yes | pre-filter | **ADAPT_TO_AWC** |
| CoordinationGoal | coord:204 | selection | yes | carries demand | **ADAPT_TO_AWC** |
| DelegationContract | coord:253 | runtime | yes | carries grant | **ADAPT_TO_AWC** |
| AuthorityModel | coord:378 | mixed | yes | **decides** | **ADAPT_TO_AWC** |
| Coordinator | coord:613 | runtime | yes | enforces | REMAIN_IN_H16 |
| AgentAssignment | coord:300 | runtime | yes | holds contract | REMAIN_IN_H16 |
| GoalOwnershipLedger | coord:342 | runtime | yes | single-owner | REMAIN_IN_H16 |
| CoordinationTrace/Result | coord:560/581 | runtime | yes | audit | REMAIN_IN_H16 |
| AgentRegistry | multi:91 | selection | yes | none | REMAIN_IN_H16 |
| KeywordRouter | multi:246 | runtime routing | yes | none | REMAIN_IN_H16 |
| LLMRouter | multi:325 | runtime routing | **no** | none | REMAIN_IN_H16 |
| MultiAgentOrchestrator | multi:384 | runtime | mixed | budget only | REMAIN_IN_H16 |

## Consumers & tests (blast radius of any change)

`coordination.py` is imported by 8 sibling modules plus the package `__init__`
(full re-export at `__init__.py:312`), 6+ examples, and directly by
`test_coordination.py`. `multi_agent.py` is imported only by the package
`__init__` (`:219`). Because the package re-exports everything, **any rename must
preserve the `agentic.agentic_framework` public names** — this is why the
compatibility strategy favors identity-preserving re-exports where semantics are
unchanged and adapters everywhere else. (See `COMPATIBILITY_RISK.md`.)

Direct + transitive test coverage: `test_coordination.py`, `test_multi_agent.py`,
`test_human_governance.py`, `test_multi_workflow_orchestration.py`,
`test_external_actions.py`, `test_parallel_execution.py`,
`test_workflow_durability.py`, `test_event_workflows.py`.
