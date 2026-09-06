"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.2.0"

#: Frozen contract identity of the registration record shape.
CONTRACT_VERSION = "ai_system_registry.v1"

#: Maturity, stated once and machine-readable. The contract modules stay contracts
#: only; 0.2.0 adds the one ruled local store (front-door FD-9.2), a sqlite file the
#: composing deployment owns. The package still resolves, gates and attests to nothing.
MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"
#: The contract modules' own posture, unchanged by the local store.
CONTRACT_MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
