"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.2.0 — canonical execution state: a deterministic, versioned, integrity-protected,
# runtime-owned representation of the execution trajectory (additive public API +
# checkpoint_version boundary for execution-state lineage). No change to exact-action
# fingerprint semantics, governance ownership, or existing checkpoint digest semantics.
# (0.1.2 hardened the exact-action contract; 0.1.1 added fail-closed default governance.)
__version__ = "0.2.0"

VERSION = __version__
