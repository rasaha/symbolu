"""Version and maturity of the approver identity JWT adapter."""

from __future__ import annotations

__version__ = "0.1.4"

#: Honest label, unchanged by AP-3. The adapter validates real signatures with a real
#: cryptographic backend and, since 2026-09-11, has been validated against one real
#: enterprise issuer within the scope ``ISSUER_VALIDATION_SCOPE`` states. It is still not
#: pilot-validated or production-certified in general, no enforcement hangs on it, and
#: the plane that composes it serves no write until the owner names one.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: What has been proven about the issuer side, and exactly how far. Stable and
#: machine-readable; every token of the name is a scope limit: the issuer (Cloudflare
#: Access), the identities (humans authenticated through the designated Google Workspace
#: group), the application (non-production), the date the owner accepted the AP-3
#: record, and the ruling that fixed the scope (AP3-D6). It does not say "production",
#: because it is not. Before 0.1.4 this label was ``IN_PROCESS_ISSUER_ONLY``.
ISSUER_VALIDATION = "CLOUDFLARE_ACCESS_HUMAN_WORKSPACE_GROUP_NONPROD_VALIDATED_2026_09_11_AP3_D6"

#: The scope behind the label, as the accepted record states it
#: (``deployment/governed-runtime-worker/AP3_ENTERPRISE_ISSUER_VALIDATION.json``,
#: ``ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`` section 20.7). A consumer that needs one
#: fact reads it here rather than parsing the label.
ISSUER_VALIDATION_SCOPE = {
    "issuer": "https://ugence.cloudflareaccess.com",
    "issuer_kind": "CLOUDFLARE_ACCESS",
    "validated_on": "2026-09-11",
    "ruling_scope": "AP3-D6",
    "identities": "HUMAN_VIA_DESIGNATED_GOOGLE_WORKSPACE_GROUP",
    "application": "NON_PRODUCTION",
    "service_identities": "NOT_COMMISSIONED",
    "production_certified": False,
    "record": "deployment/governed-runtime-worker/AP3_ENTERPRISE_ISSUER_VALIDATION.json",
    "acceptance_report": "deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md@fb373ce9",
    "accepted_by": "Rakesh Mohan — Founder, Ugence Labs",
}

ENFORCEMENT_ENABLED = False
