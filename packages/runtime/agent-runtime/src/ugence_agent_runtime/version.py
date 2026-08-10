"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.4.0 — H22-B deterministic multi-workflow coordination: an additive orchestration layer
# above the single-workflow runtime (WorkflowPortfolio + cross-workflow dependency graph +
# eligibility classification + a deterministic scheduler with priority/fairness/aging) that
# decides WHICH prepared workflow receives the next H22-A quantum, and why. It consumes the
# unchanged advance_workflow seam and adds no concurrency, no shared budget/resource ledger,
# no portfolio checkpoint/recovery, and no compensation. Governance stays entirely below it:
# the scheduler selects a workflow, it never authorizes that workflow's task. No change to
# exact-action fingerprint semantics, governance ownership, canonical execution state,
# checkpoint digest semantics, or recovery behavior.
# (0.3.0 added the H22-A bounded-advancement seam; 0.2.0 added canonical execution state;
# 0.1.2 hardened the exact-action contract; 0.1.1 added fail-closed default governance.)
__version__ = "0.4.0"

VERSION = __version__
