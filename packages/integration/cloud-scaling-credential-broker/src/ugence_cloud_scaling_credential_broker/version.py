"""Distribution version, read statically by the build backend.

``0.1.0`` is Cloud Scaling Phase 5X: the Credential Broker seam and port. Neighbours, as
of ``0.1.0``: Risk Authority ``0.8.0``, ``cloud-scaling-action-admission`` ``0.1.0``,
``execution-reservation`` ``0.1.0``, none of them modified by this package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
