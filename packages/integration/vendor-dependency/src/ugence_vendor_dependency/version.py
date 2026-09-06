"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.2.0"

#: Frozen contract identity of the declaration record shape.
CONTRACT_VERSION = "vendor_dependency.v1"

#: Maturity, stated once and machine-readable. Since 0.2.0 the package also keeps
#: those records in one tenant-bound local file (front-door ruling FD-13.2). It still
#: records what a declarer asserted about a vendor dependency and evaluates nothing.
MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"

#: The contract surface itself is unchanged by the store: the record types, refusal
#: reasons, selectors and port are exactly what 0.1.0 shipped.
CONTRACT_MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
