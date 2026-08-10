"""H22-B — deterministic multi-workflow coordination for the Agent Runtime.

This subpackage is the coordination layer that sits **above** the single-workflow runtime
and decides *which* prepared workflow receives the next H22-A bounded execution quantum,
and *why*. It answers exactly one question:

    Given N prepared independent workflows, which workflow is eligible to receive the next
    execution quantum, and why?

It provides a :class:`WorkflowPortfolio` (orchestration-state aggregate), a cross-workflow
:class:`DependencyGraph`, deterministic eligibility classification, and a
:class:`PortfolioScheduler` that applies explicit **priority**, bounded starvation-prevention
**aging**, and deterministic **fairness** to grant one quantum per round through the
unchanged ``advance_workflow`` seam.

**Scope (H22-B only).** Deterministic *interleaving*, NOT simultaneous execution. No
concurrency, no shared budget/resource ledger, no portfolio checkpoint/recovery, no failure
propagation / compensation engine, no peer-to-peer agent messaging, no agent/model
selection. Governance stays entirely below this layer: the scheduler selects a workflow, it
never authorizes that workflow's task.

Dependency direction is orchestration → runtime: this package imports the runtime's public
contracts; the runtime engine never imports orchestration, so the single-workflow runtime
stays usable without it.
"""
from __future__ import annotations

from .dependencies import (
    DependencyGraph,
    DependencyState,
    DependencyType,
    WorkflowDependency,
)
from .portfolio import (
    PortfolioStatus,
    PortfolioWorkflowEntry,
    WorkflowPortfolio,
    WorkflowPriority,
    priority_rank,
)
from .scheduling import (
    PortfolioScheduler,
    PortfolioStepReason,
    PortfolioStepResult,
    SchedulingPolicy,
    SelectionReason,
    WorkflowEligibility,
)

__all__ = [
    # portfolio aggregate + registration
    "WorkflowPortfolio",
    "PortfolioWorkflowEntry",
    "PortfolioStatus",
    "WorkflowPriority",
    "priority_rank",
    # dependency graph
    "DependencyGraph",
    "DependencyType",
    "DependencyState",
    "WorkflowDependency",
    # scheduling
    "PortfolioScheduler",
    "SchedulingPolicy",
    "PortfolioStepResult",
    "PortfolioStepReason",
    "SelectionReason",
    "WorkflowEligibility",
]
