"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package.
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen identity of the binding convention: subject kind, consumer-ref shape and
#: the reason code a consumed approval contributes to composition.
CONTRACT_VERSION = "governed_review.v1"

#: Maturity, stated once and machine-readable. The package binds an approval to a
#: proposal and consumes it; it never approves, authenticates, mints authority,
#: signals, resumes or executes. The ledger and directory it composes are themselves
#: REFERENCE_GRADE_SHADOW_ONLY, and the runtime it feeds invokes fixture providers.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"
ENFORCEMENT_ENABLED = False
