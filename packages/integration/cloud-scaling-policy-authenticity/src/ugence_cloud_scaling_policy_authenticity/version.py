"""Distribution version.

``0.1.0`` shipped Phase 5B-0B, which added a distribution and changed no neighbour's version.
``0.2.0`` is Phase 5B-1: gate 11 reconciles a supplied candidate against the resolved policy,
``candidate_digest_fact`` moved into the verified half, and
:data:`~.identifiers.VERIFICATION_PROFILE_VERSION` moved to ``v2`` with it.

Neighbours, as of ``0.2.0``: Phase 5A (``ugence-cloud-scaling-authorization-contracts``) is at
``0.2.0`` — 5B-1 moved it, by binding the policy coordinate inside the candidate, and one of
its now-eleven frozen digests moved. The Policy Authority stays at ``0.1.0``, unmodified.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

#: Cloud Scaling Phase 5B-1 — decision-scope repair, on the 5B-0B foundation.
__version__: Final[str] = "0.2.0"
