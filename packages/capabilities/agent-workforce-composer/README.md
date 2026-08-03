# Ugence Agent Workforce Composer — P1

Deterministic, **offline** planning capability that answers exactly one question:

> Which workflow nodes may be performed by AI agents, what capabilities do those
> roles require, and which registered agents are eligible or ineligible under
> frozen hard constraints?

It is **not** a human-hiring product and **not** a runtime. This package is
**P1**: canonical planning objects, a read-only adapter over the Policy Workflow
Compiler `WorkflowIR`, and deterministic hard-constraint agent eligibility.

- Distribution: `ugence-agent-workforce-composer`
- Namespace: `ugence_agent_workforce_composer`
- Distribution / product version: `0.1.0`
- Contract version: `awc.v1`

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

## What P1 does NOT implement

soft scoring · weighted ranking · winner selection · team composition · permission
grant construction · fallback-chain selection · runtime handoff · H16 migration ·
Agent Runtime / H22 adapters · Model Selection invocation · live registration ·
agent execution. An `ELIGIBLE` result means *only*: no currently evaluated hard
constraint disqualifies this agent for this role under the pinned inputs. It never
means selected, recommended, best, authorized, approved for execution, assigned, or
production-safe. See [`docs/NEXT_PHASES.md`](docs/NEXT_PHASES.md).

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
