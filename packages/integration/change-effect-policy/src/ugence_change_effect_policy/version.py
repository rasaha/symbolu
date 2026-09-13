"""Single source of truth for the package version and maturity posture.

Read statically by the build backend so building a wheel never imports the package.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the policy artifact's shape.
CONTRACT_VERSION = "change_effect_policy.v1"

#: The rule version the artifact's membership was ruled against.
RULE_VERSION = "GERL target classification 4.2.10, with the recorded erratum"

#: Maturity, stated once and machine-readable. The initial artifact is non-operative
#: by construction: an empty delegation table, and no mapping content anywhere.
MATURITY = "REFERENCE_GRADE_CONTRACT_ONLY"
ENFORCEMENT_ENABLED = False
