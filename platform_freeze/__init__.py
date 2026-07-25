"""Platform freeze tooling — repository & release tooling for Decision Governance Platform v1.0.

Freezes and verifies the validated governance architecture: reproducible freeze
manifest, canonical invariant register, public-API snapshots + compatibility
checker, dependency-direction/package-ownership verification, and a change-
classification maintenance gate. This is tooling, NOT a runtime platform
dependency — the frozen platform packages do not import it.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
