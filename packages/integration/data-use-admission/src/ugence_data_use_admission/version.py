"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.2.0"

#: Frozen contract identity of the declaration record shape.
CONTRACT_VERSION = "data_use_admission.v1"

#: Maturity, stated once and machine-readable. The package records what a declarer
#: asserted about data and admits, classifies and enforces nothing; since 0.2.0 it also
#: keeps those records in one tenant-bound local sqlite file (FD-12.2), which changes
#: where a declaration lives and nothing about what it means.
MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"

#: What the record shape itself is, unchanged by the store: contracts only.
CONTRACT_MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
