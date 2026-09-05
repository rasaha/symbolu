"""Distribution version, read statically by the build backend.

``0.1.0`` is Cloud Scaling Phase 5C: the composition package that implements Risk
Authority's ``ActionGatePort`` for capacity actions and calls the ``ActionAdmissionSeam``.
Neighbours, as of ``0.1.0``: Risk Authority ``0.8.0``, Phase 5A ``0.2.0``, 5B-4
``cloud-scaling-envelope-issuance`` ``0.1.0``, none of them modified by this package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
