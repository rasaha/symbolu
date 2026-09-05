"""Version and maturity of the approver identity JWT adapter."""

from __future__ import annotations

__version__ = "0.1.0"

#: Honest label. The adapter validates real signatures with a real cryptographic
#: backend, but the only issuer it has ever been run against is the in-process test
#: issuer in this package's own suite. Nothing here is validated against an
#: enterprise identity provider, and nothing here is pilot-validated or
#: production-certified.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: What has and has not been proven about the issuer side.
ISSUER_VALIDATION = "IN_PROCESS_ISSUER_ONLY"

ENFORCEMENT_ENABLED = False
