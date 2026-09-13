"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the record shapes.
CONTRACT_VERSION = "change_effect_records.v1"

#: The rule version these shapes were scoped against, and its review standing.
RULE_VERSION = "GERL target classification 4.2.10, with the recorded erratum"

#: Maturity, stated once and machine-readable. Stage 1 substrate: inert by
#: construction, with no producer, no consumer and no runtime path.
MATURITY = "REFERENCE_GRADE_CONTRACT_ONLY"
ENFORCEMENT_ENABLED = False
