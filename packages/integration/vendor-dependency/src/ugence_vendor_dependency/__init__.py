"""Ugence Vendor Dependency — the contracts-only record of declared vendor dependencies.

    THIS PACKAGE RECORDS WHAT A DECLARER ASSERTED ABOUT A VENDOR DEPENDENCY.
    IT NEVER RESOLVES, VERIFIES, SCORES, GRADES, CONTACTS, PERSISTS OR DECIDES.

Contracts only, under ``docs/architecture/ADR_UGENCE_VENDOR_RISK_SCOPING.md``:
record types, refusal reasons, pure selectors and one read-only Protocol. **No
store, no connector, no gateway, no scorer, no clock** — nothing here could reach a
vendor, a policy, a store or a network, so the lines the rulings draw are held
structurally rather than by discipline.

* VR-1 — a record of vendor dependencies; not a gateway, a supplier system, a
  registry or an authority.
* VR-2 ``BINDING_ONLY`` — each declaration binds directly to exactly one canonical
  ``AssessedSystemBinding``; the registry is never imported and a registration is
  never accepted as an alternative identity.
* VR-3 ``SEPARATE_OPAQUE_RISK_LABEL`` — the posture is a ``VendorRiskLabel``, a
  different dimension from data classification, and uninterpreted.
* VR-4 ``POLICY_REF_STRING`` — one opaque ``policy_ref``, recorded and never
  resolved, verified, interpreted or fetched; Policy Authority is never imported.
* VR-5 — ``VendorRiskLabel`` and ``AssessedSystemBinding`` are re-exported from
  governance-contracts, never redefined; ``vendor_ref`` stays a package-local string.

A declaration is a record, not a permission.
"""

from __future__ import annotations

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    SystemBindingAuthenticityStatus,
    VendorRiskLabel,
)

from .declaration import (
    DECLARATION_ID_PREFIX,
    VendorDependencyDeclaration,
    declaration_id_for,
    require_admissible_supersession,
    supersession_refusals,
    validity_from_dict,
    validity_to_dict,
)
from .errors import (
    ContractViolation,
    DeclarationSupersessionError,
    VendorDependencyError,
)
from .selectors import (
    VendorDependencyPort,
    declared_at,
    select_by_policy_ref,
    select_by_risk_posture,
    select_for_system,
    select_for_tenant,
    select_for_vendor,
    supersession_chain,
)
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # the system identity and the label, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus", "VendorRiskLabel",
    # the record
    "VendorDependencyDeclaration", "declaration_id_for", "DECLARATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    # the read seam and its pure selectors
    "VendorDependencyPort", "declared_at", "select_for_tenant", "select_for_vendor",
    "select_for_system", "select_by_risk_posture", "select_by_policy_ref",
    "supersession_chain",
    # errors
    "VendorDependencyError", "ContractViolation", "DeclarationSupersessionError",
]
