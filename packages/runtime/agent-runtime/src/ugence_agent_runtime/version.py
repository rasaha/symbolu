"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.3.0 — H22-A bounded workflow advancement: an additive, deterministic seam letting an
# external orchestrator create a workflow without draining it (prepare_workflow) and
# advance it one bounded quantum at a time (advance_workflow) to a stable, checkpointed
# boundary. No change to exact-action fingerprint semantics, governance ownership,
# canonical execution state, checkpoint digest semantics, or recovery behavior;
# start_workflow keeps its run-to-stable-state behavior. Not full H22 (no portfolio
# scheduler, no cross-workflow dependencies, no concurrency).
# (0.2.0 added canonical execution state; 0.1.2 hardened the exact-action contract;
# 0.1.1 added fail-closed default governance.)
__version__ = "0.3.0"

VERSION = __version__
