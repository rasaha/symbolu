"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.1.1 — post-merge governance-safety correction: fail-closed default governance,
# exact-action proposal-fingerprint binding, honest compatibility coexistence.
__version__ = "0.1.1"

VERSION = __version__
