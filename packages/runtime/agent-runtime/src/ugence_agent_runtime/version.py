"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.5.0 — H22-C durable multi-workflow orchestration: an additive layer above H22-B that makes
# the portfolio/team coordinator durable, reconstructable, auditable, and safely controllable
# across failure/restart. Adds a versioned PortfolioCheckpoint (referencing — never copying —
# the underlying runtime checkpoints, and never duplicating canonical execution state), a
# neutral portfolio checkpoint store + in-memory reference, side-effect-free portfolio recovery
# with explicit post-recovery continuation, an append-only orchestration audit trace ordered by
# a logical sequence, bounded failure propagation (ISOLATE_WORKFLOW default / FAIL_DEPENDENTS /
# FAIL_PORTFOLIO), and cooperative, idempotent cancellation scopes (WORKFLOW_ONLY /
# DEPENDENT_SUBGRAPH / PORTFOLIO_ALL). It changes no single-workflow execution truth: no change
# to exact-action fingerprint semantics, governance ownership, canonical execution state,
# checkpoint digest semantics, or single-workflow recovery. Recovery performs zero provider,
# governance, and advancement calls. No true concurrency, resource ledger, shared budget, or
# compensation (those remain H22-D).
# (0.4.0 added the H22-B deterministic coordination layer; 0.3.0 added the H22-A bounded-
# advancement seam; 0.2.0 added canonical execution state; 0.1.2 hardened the exact-action
# contract; 0.1.1 added fail-closed default governance.)
__version__ = "0.5.0"

VERSION = __version__
