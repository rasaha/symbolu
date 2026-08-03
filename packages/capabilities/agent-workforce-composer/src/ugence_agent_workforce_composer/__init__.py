"""Ugence Agent Workforce Composer — canonical planning capability (P1).

The Agent Workforce Composer is a deterministic, offline planning capability. It
is **not** a human-hiring product and **not** a runtime. P1 answers exactly one
question:

    Which workflow nodes may be performed by AI agents, what capabilities do those
    roles require, and which registered agents are eligible or ineligible under
    frozen hard constraints?

Deterministic pipeline::

    serialized Policy Workflow Compiler WorkflowIR (workflow_ir.v1)
            ↓  CompilerWorkflowAdapter (data-only, read-only)
    WorkflowRoleRequirement[]  +  NonAgentDisposition[]   (total node accounting)
            ↓  AgentRegistrySnapshot + EnterpriseAgentPolicy + EligibilityPolicy
    AgentEligibilityGate (hard constraints, fail-closed)
            ↓
    AgentEligibilityResult for every role × agent pair (total agent accounting)
            ↓
    EligibleAgentSet / EliminatedAgentSet / EligibilityExplanation / EligibilityReplayRecord

This is a **leaf capability**: it depends only on the Python standard library and
``pydantic``. It never imports ``agentic.agentic_framework`` (H16), Agent Runtime,
H22, Model Selection, AI Hiring, Procurement, ActionGate, Action Clearance, or
StoryGraph. The compiler seam is *data-only* — a serialized ``workflow_ir.v1``
document — so AWC builds, installs and imports outside the monorepo.

NOT implemented in P1 (see ``docs/NEXT_PHASES.md``): ranking, scoring, winner
selection, team composition, permission assignment, fallback selection, runtime
handoff, H16 migration, Agent Runtime / H22 adapters, Model Selection invocation,
live registration, and agent execution.

Import the public surface from ``ugence_agent_workforce_composer.api``.
"""
from __future__ import annotations

from .version import CONTRACT_VERSION, VERSION, __version__, version_info

__all__ = ["__version__", "VERSION", "CONTRACT_VERSION", "version_info"]
