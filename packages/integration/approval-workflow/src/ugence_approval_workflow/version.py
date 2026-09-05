"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.2.0"

#: Frozen contract identity of the consumption-key serialization and event shapes.
CONTRACT_VERSION = "approval_workflow.v1"

#: Maturity, stated once and machine-readable. The package records and reports an
#: approval; it never approves, authenticates, mints authority or executes.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"
ENFORCEMENT_ENABLED = False
