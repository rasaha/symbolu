"""Version and maturity of the governed runtime worker.

Read statically by the build backend so building a wheel imports nothing.
"""

from __future__ import annotations

__version__ = "0.1.1"

DEPLOYMENT_NAME = "governed-runtime-worker"

#: Honest label. Every provider this worker invokes is a fixture, the only identity
#: adapter it can compose has been validated against an in-process issuer only, and
#: nothing it records is enforced anywhere. ``UGENCE_REVIEW_DEPLOYMENT_MODE=production``
#: selects a fail-closed posture; it certifies nothing.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: Never true here. The worker composes packages that each declare the same, and a
#: test asserts it across all of them.
ENFORCEMENT_ENABLED = False
