"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the registration record shape.
CONTRACT_VERSION = "ai_system_registry.v1"

#: Maturity, stated once and machine-readable. Contracts only: the package records
#: what an administrator asserted and resolves, gates and attests to nothing.
MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
