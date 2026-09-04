"""Distribution version, read statically by the build backend.

``0.1.0`` is Cloud Scaling Phase 5D: the bounded execution seam. Neighbours, as of
``0.1.0``: Cloud Scaling Operations ``0.1.2``, ``cloud-scaling-credential-broker`` ``0.1.0``,
``execution-reservation`` ``0.1.0``, Risk Authority ``0.8.0``, none of them modified.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
