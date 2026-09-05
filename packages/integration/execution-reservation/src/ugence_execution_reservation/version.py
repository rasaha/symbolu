"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the execution key serialization and event shapes.
CONTRACT_VERSION = "execution_reservation.v1"

#: Maturity, stated once and machine-readable. Ratified decision D-4: the
#: enforcement gate stays closed until the PRIOR_CONSUMPTION signal can be
#: emitted at trust Level 2 and reconciliation wiring exists.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"
ENFORCEMENT_ENABLED = False
