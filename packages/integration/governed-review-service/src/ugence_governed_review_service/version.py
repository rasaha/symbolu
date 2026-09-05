"""Version, contract and maturity of the governed review service."""

from __future__ import annotations

__version__ = "0.2.0"

#: The wire contract this release presents: the five routes of the screen/API audit,
#: v2 since 0.2.0 widened the decision and run-detail answers with the linkage (HE-1,
#: HE-5). No sixth route.
CONTRACT_VERSION = "governed_review_service.v2"

#: Honest label. The service records decisions whose approver is a PRESENTED reference:
#: no identity provider integration exists, so nothing here proves who decided. Every
#: decision it records feeds a runtime that invokes fixture providers.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: What the service can say about the approver on every decision it records.
IDENTITY_PROOF = "PRESENTED_UNPROVEN"

ENFORCEMENT_ENABLED = False
