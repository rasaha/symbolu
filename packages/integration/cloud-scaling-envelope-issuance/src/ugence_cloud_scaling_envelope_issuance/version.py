"""Distribution version, read statically by the build backend.

``0.1.0`` is Cloud Scaling Phase 5B-4: the composition package that calls Risk Authority's
Phase 5 envelope issuance seam with the 5A candidate and the 5B-0A and 5B-0B verifiers.
Neighbours, as of ``0.1.0``: Risk Authority ``0.6.0`` (the seam), Phase 5A ``0.2.0``,
Phase 5B-0A ``0.2.0`` and Phase 5B-0B ``0.9.0``, none of them modified by this package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
