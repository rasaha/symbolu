"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the grant serialization and event shapes.
CONTRACT_VERSION = "authority_directory.v1"

#: Maturity, stated once and machine-readable. The directory reports grants; it
#: decides nothing, authenticates nobody, and holds custody of nothing.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"
ENFORCEMENT_ENABLED = False
