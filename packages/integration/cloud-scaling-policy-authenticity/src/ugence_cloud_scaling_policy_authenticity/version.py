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

#: ``0.5.0`` was 5B-3, which promoted ``policy_type`` and added ``capacity_bounds_fact``, so
#: the partition, the artifact digest and the profile version moved together to ``v3``.
#:
#: ``0.6.0`` is Cloud Scaling R-12b — **fixture pins only**, and the profile stays at ``v3``.
#: This package's verification source is untouched: its occurrence gate reads candidate facts
#: by name, and Phase 5A re-sourcing those facts from the digest-bound decision snapshot
#: satisfies it without a change here. What moved is the Phase 5A mirror the suite pins.
__version__: Final[str] = "0.6.0"
