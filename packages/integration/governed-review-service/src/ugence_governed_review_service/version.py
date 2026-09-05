"""Version, contract and maturity of the governed review service."""

from __future__ import annotations

__version__ = "0.3.0"

#: The wire contract this release presents: the five routes of the screen/API audit,
#: v2 since 0.2.0 widened the decision and run-detail answers with the linkage (HE-1,
#: HE-5); v3 since 0.3.0 reads one opaque proof header on the decision route and
#: widens the decision answer with ``authentication_reference``, ``tenant_source`` and
#: ``assurance`` (AI-A). No sixth route.
CONTRACT_VERSION = "governed_review_service.v3"

#: Honest label. The service records decisions whose approver is a PRESENTED reference:
#: no identity provider integration exists, so nothing here proves who decided. Every
#: decision it records feeds a runtime that invokes fixture providers.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: What the service can say about the approver on every decision it records. The
#: identity port (AI-A) exists, but its only adapter is a fixture that proves nothing;
#: a decision is labelled ``IDP_AUTHENTICATED`` only by a real adapter (AI-C), and none
#: exists in this repository.
IDENTITY_PROOF = "PRESENTED_UNPROVEN"

ENFORCEMENT_ENABLED = False
