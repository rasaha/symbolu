"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.1.2 — exact-action contract hardening: deeply immutable proposal identity,
# correlation folded into the fingerprint with mandatory binding, inclusive expiry.
# (0.1.1 added fail-closed default governance and exact-action fingerprint binding.)
__version__ = "0.1.2"

VERSION = __version__
