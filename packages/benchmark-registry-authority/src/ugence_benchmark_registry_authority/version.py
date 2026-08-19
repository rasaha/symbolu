"""Single source of truth for the distribution version.

BR-2A ships ``0.1.0``: registry and exact-resolution **contracts** only. The
ratified version ladder for this distribution is BR-2A ``0.1.0`` (contracts),
BR-2B ``0.2.0`` (admission and the process-local registry), BR-2C ``0.3.0``
(publisher trust and signature verification) and BR-2D ``0.4.0`` (durable store
and production composition). Nothing beyond ``0.1.0`` exists yet, here or
anywhere else in this repository.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
