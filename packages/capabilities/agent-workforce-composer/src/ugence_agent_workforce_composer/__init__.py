"""Ugence Agent Workforce Composer — canonical planning capability (P1 + P2 + P2.1).

The Agent Workforce Composer is a deterministic, offline planning capability. It
is **not** a human-hiring product and **not** a runtime. It answers two questions,
in order:

    P1 — Which workflow nodes may be performed by AI agents, what capabilities do
    those roles require, and which registered agents are eligible or ineligible
    under frozen hard constraints?

    P2 — Over the P1-eligible sets only: how are eligible agents ranked, which
    teams compose, what permission bounds does the proposal carry, and what
    fallbacks apply — culminating in an immutable ``AgentTeamPlan``?

P2.1 adds ``workflow_ir.v2`` compiler support alongside v1, with overlay reduction
and a v1/v2 equivalence harness.

Deterministic P1 pipeline::

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

NOT implemented (see ``docs/NEXT_PHASES.md``; every item is ``false`` in
``version_info()``): the Governance Studio API, permission assignment and granting
— P2 proposes bounds and grants nothing — runtime handoff, runtime execution, H16
migration, H22 scheduling, Model Selection interop, live registry ingestion, live
availability, pilot validation, and production certification.

Import the public surface from ``ugence_agent_workforce_composer.api``.
"""
from __future__ import annotations

from .version import CONTRACT_VERSION, VERSION, __version__, version_info

__all__ = ["__version__", "VERSION", "CONTRACT_VERSION", "version_info"]
