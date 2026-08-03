# Ugence Agent Workforce Composer — P1 + P2

Deterministic, **offline** planning capability. It is **not** a human-hiring
product and **not** a runtime.

- **P1** answers: which workflow nodes may be performed by AI agents, what
  capabilities do those roles require, and which registered agents are eligible or
  ineligible under frozen hard constraints? (adapter + hard-constraint eligibility)
- **P2** answers, over the P1-eligible sets only: how are eligible agents ranked,
  which bounded exact multi-role team is optimal under team hard constraints, what
  least-privilege permission bound is proposed, and what ordered fallbacks apply —
  producing an immutable **AgentTeamPlan**. P2 **grants nothing, authorizes
  nothing, schedules nothing, and executes nothing.**

- Distribution: `ugence-agent-workforce-composer`
- Namespace: `ugence_agent_workforce_composer`
- Distribution / product version: `0.2.0`
- Contract versions: `awc.v1` (P1, preserved), `awc.composition.v1` (P2, additive)

## Pipeline

```
serialized Policy Workflow Compiler WorkflowIR (workflow_ir.v1)
        ↓  CompilerWorkflowAdapter (data-only, read-only)
WorkflowRoleRequirement[]  +  NonAgentDisposition[]      (total node accounting)
        ↓  AgentRegistrySnapshot + EnterpriseAgentPolicy + EligibilityPolicy
AgentEligibilityGate (hard constraints, fail-closed)
        ↓
AgentEligibilityResult for every role × agent pair       (total agent accounting)
        ↓
EligibleAgentSet / EliminatedAgentSet / EligibilityExplanation / EligibilityReplayRecord
```

## What P1 implements

canonical immutable planning models · compiler `WorkflowIR` adaptation · workflow-node
disposition · workflow-role requirements · immutable agent capability profiles ·
capability evidence & provenance (DECLARED / MEASURED / OBSERVED) · frozen registry
snapshots · enterprise hard constraints · hard-constraint eligibility · elimination
reason taxonomy · complete candidate accounting · deterministic fingerprints ·
deterministic explanation · replay records · synthetic workflows & registries ·
independent distribution · offline CLI · tests, docs, CI.

## P2 pipeline (over P1-eligible sets only)

```
RoleEligibilityReport[]  → AgentRankingPolicy      → RoleCandidateRanking[]
                         → RoleDependencyGraph
                         → TeamCompositionPolicy    → bounded exact search
                         → TeamCompositionResult    (EXACT_OPTIMUM | NO_FEASIBLE_TEAM | SEARCH_SPACE_EXCEEDED)
                         → PermissionBoundingPolicy → PermissionBoundProposal[]  (least-privilege; proposal only)
                         → AgentFallbackPolicy      → RoleFallbackPlan[]
                         → AgentTeamPlan + SelectionExplanation + CompositionReplayRecord
```

P2 implements: deterministic evidence-backed ranking (integer basis-point scores,
exactly reconstructable from criterion contributions); a role dependency/interface
graph; bounded exact team composition (deterministic branch-and-bound, proven
against a brute-force oracle); least-privilege permission-bound **proposals**;
offline primary + fallback planning; and the immutable **AgentTeamPlan** with
selection explanation, replay and diff.

## What this package does NOT implement

permission granting · runtime execution · live availability · runtime fallback /
reassignment · H16 migration · Agent Runtime / H22 adapters · Model Selection
invocation · workflow scheduling · large-scale approximate solving · live
registration · agent execution. An `ELIGIBLE` result and an AgentTeamPlan are
**proposals** — never selection-for-execution, authorization, permission grant,
assignment, or production certification. A `PermissionBoundProposal` states: *"This
is a planning-time permission-bound proposal. It does not grant, authorize,
provision or execute any permission."* See [`docs/NEXT_PHASES.md`](docs/NEXT_PHASES.md).

## Install & use

```bash
pip install ugence-agent-workforce-composer
ugence-agent-workforce-composer version
ugence-agent-workforce-composer demo procurement
```

```python
import ugence_agent_workforce_composer.api as awc

pkg = ...  # a serialized workflow_ir.v1 document (dict / JSON)
adaptation = awc.adapt_compiled_workflow(pkg)
report = awc.evaluate_registry_for_role(role, snapshot, enterprise_policy,
                                        eligibility_policy, logical_time)
```

## Boundaries

Leaf capability: **standard library + `pydantic` only**. The compiler seam is
**data-only** (a serialized `workflow_ir.v1` document), so this package builds,
installs and imports outside the monorepo and never imports
`agentic.agentic_framework` (H16), Agent Runtime, H22, Model Selection, AI Hiring,
Procurement, ActionGate, Action Clearance, or StoryGraph.

## Verify

```bash
PYTHONPATH=src python -m pytest tests -q
python verify_agent_workforce_composer_distribution.py
```

Maturity: `pilot_validated=false`, `production_certified=false`. Workflow
adaptation and agent eligibility are implemented and locally verified over frozen
synthetic fixtures; agent ranking, team composition and runtime use remain
unimplemented.
