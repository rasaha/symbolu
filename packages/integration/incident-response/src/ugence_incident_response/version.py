"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the record shapes.
CONTRACT_VERSION = "incident_response.v1"

#: Maturity, stated once and machine-readable. Records only: the package emits
#: records and proposals and acts on nothing.
MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
