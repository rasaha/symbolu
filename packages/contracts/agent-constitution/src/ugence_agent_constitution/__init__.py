"""Ugence Agent Constitution — AC-0 contracts.

Immutable, versioned, content-addressed artifacts for an agent's constitutional
text, plus the deterministic, fail-closed validation that decides whether such an
artifact is well-formed.

This package is a **leaf contract**: pydantic and the standard library, and no
other Ugence package. It is not an authority. It ratifies nothing, approves
nothing, authorizes nothing, resolves no capability, and binds nothing at runtime.

The curated surface is :mod:`ugence_agent_constitution.api`; import from there.
"""

from __future__ import annotations

from .api import *  # noqa: F401,F403
from .api import __all__ as _API_ALL
from .version import DISTRIBUTION_VERSION as __version__

__all__ = list(_API_ALL)
