"""Distribution version. Phase 5B-0B ships at 0.1.0 and changes no neighbour's version.

Phase 5A (``ugence-cloud-scaling-authorization-contracts``) stays at ``0.1.0`` with all ten
frozen digests unmoved, and the Policy Authority stays at ``0.1.0``. This package adds a
distribution; it modifies neither.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

#: Cloud Scaling Phase 5B-0B — policy authenticity foundation.
__version__: Final[str] = "0.2.0"
