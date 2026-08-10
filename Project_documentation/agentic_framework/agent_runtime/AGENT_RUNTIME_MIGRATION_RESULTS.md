# Agent Runtime — Migration Results (Deliverable 8)

Results of the additive migration build. The new runtime is a **proposer**; governance is the AI
Control Plane's. The legacy `agentic/agentic_framework/` package is **untouched** (rollback source).

Labels: `FACT` (measured) · `INTERPRETATION`.

## 1. Headline
`FACT`. A new `agent_runtime_migration/` package (2,446 LOC, 69 modules) implements the full loop —
Goal → Plan → Action → **native CER** → AI Control Plane → (if eligible) governed executor →
observation → memory → reflection — with **0 governance-boundary violations** across a 10-scenario
deterministic suite and **0 lines changed** in ActionGate, ACP, or CER. The legacy package (68,097
LOC, 131 modules) is unchanged.

## 2. Test results
`FACT`. **39 migration tests pass** (contracts+CER 13, runtime core 9, tools+execution 10,
forbidden-import 2, compatibility 5). The wider repository suite is unaffected (this milestone added
only the new package + docs).

## 3. Benchmark (`benchmark/results.json`)
`FACT`. **10/10 scenarios** with correct status; **10/10** governed-execution counts correct;
**governance_boundary_violations = 0**.
| Scenario | Status | Governed tool ran? |
|---|---|---|
| read_only_research | completed | n/a (local ×1) |
| multi_step_workflow | completed | n/a (local ×3) |
| kubernetes_scale_proceed | completed | yes ×1 (PROCEED) |
| database_mutation_proceed | completed | yes ×1 (PROCEED) |
| denied_action | stopped | **no** (BLOCKED) |
| acp_operational_hold | awaiting_human | **no** (HELD_BY_ACP) |
| execution_failure | stopped | local tool raised |
| cancellation | cancelled | no |
| human_intervention | awaiting_human | **no** (PENDING) |
| observe_reflect_replan | completed | no (denied → replan) |

Every non-eligible governed action left the tool **unrun**; every eligible action ran exactly once.

## 4. Measurements (§12)
`FACT`.
- **CER correctness:** governed scenarios carry a v2 action digest; deterministic; provenance
  excluded; material change alters identity (tested).
- **Trace completeness:** every non-cancelled run emits OBSERVED + REFLECTED.
- **Memory-update equivalence:** every observation is recorded (the return path).
- **Governance-boundary violations:** **0**.
- **Repository impact:** ActionGate **0**, ACP **0**, CER **0**; new package **2,446 LOC / 69
  modules**; legacy **68,097 LOC / 131 modules untouched**.
- **Dependency direction:** runtime → frozen control plane (one-way); no circular import.

## 5. Intended differences vs the legacy runtime (not defects)
`INTERPRETATION`. The legacy runtime is not executed in the benchmark (its path makes its own
authoritative allow/deny and its import pulls research code). The deliberate differences:
1. runtime no longer owns authoritative allow/deny — the AI Control Plane decides eligibility;
2. governed tools run only via the governed executor on a control-plane execution reference;
3. approvals bind in ActionGate, not the runtime (the runtime only requests human input);
4. uncertainty signals are advisory (may raise scrutiny, never authorize);
5. research-signal governance (CG/JEPA/vritti/sovereign) is absent from the production runtime.

## 6. Verdicts (§15)
`FACT`.
### Code validity → `MIGRATION_CODE_VALIDATED`
Clear ownership, no hidden governance authority, deterministic, typed, explicit failure behavior,
tested (39), documented, no research-only dependency, no tool-execution bypass. (`AGENT_RUNTIME_VALID_CODE_POLICY.md`.)

### Responsibility boundary → `RUNTIME_BOUNDARY_CLEAN`
The runtime emits no authoritative allow/deny; it cannot override ActionGate or ACP; governed tools
cannot execute without a control-plane execution reference; the forbidden-import test proves no
duplicate authority and no research-signal governance in the runtime.

### Legacy compatibility → `LEGACY_COMPATIBILITY_SUPPORTED`
Supported legacy shapes migrate and run (local + governed-via-CER); unsupported legacy governed
actions fail explicitly; deprecation warnings fire; legacy governance authority is refused; the
legacy package is untouched and available for rollback. (`AGENT_RUNTIME_LEGACY_COMPATIBILITY.md`.)

### Migration readiness → `AGENT_RUNTIME_MIGRATION_READY_WITH_LIMITATIONS`
`FACT`. All readiness criteria are met: valid runtime loop; native CER generation; working AI
Control Plane boundary; governed execution cannot be bypassed; observation returns to
memory/reflection; no authoritative governance inside the runtime; no research-only production
imports; compatibility documented; legacy package untouched and available for rollback; all
migration tests green; no unresolved high-severity defect.
`INTERPRETATION` — **limitations** (scope, not defects): governed actions are limited to the three
frozen CER profiles (`kubernetes.scale.v1`, `kubernetes.rollout.v1`, `database.mutation.v1`) — a new
domain needs a new CER profile + ACP adapter; planning uses a deterministic/injectable planner (an
LLM-driven planner implements the same interface but is not wired in this milestone); replan
currently drops the denied action rather than substituting an alternative; the control plane is
shadow-only over fixtures (no live cluster/database). These bound breadth, not correctness — hence
`…_WITH_LIMITATIONS`.

## 7. Deliverables map
`FACT`. (1) `AGENT_RUNTIME_MIGRATION_INVENTORY.md`, (2) `agent_runtime_migration_inventory.json`,
(3) `AGENT_RUNTIME_MIGRATION_ARCHITECTURE.md`, (4) `AGENT_RUNTIME_VALID_CODE_POLICY.md`,
(5) `AGENT_RUNTIME_CONTROL_PLANE_BOUNDARY.md`, (6) `AGENT_RUNTIME_LEGACY_COMPATIBILITY.md`,
(7) `AGENT_RUNTIME_MIGRATION_TEST_PLAN.md`, (8) this file, (9) `agent_runtime_migration/` package,
(10) unit + (11) integration + (12) compatibility + (13) forbidden-import tests,
(14) `agent_runtime_migration/benchmark/` runner, (15) `benchmark/results.json`.
