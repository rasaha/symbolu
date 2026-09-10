"""Ugence Vendor Dependency — the record of declared vendor dependencies, and its one
local home.

    THIS PACKAGE RECORDS WHAT A DECLARER ASSERTED ABOUT A VENDOR DEPENDENCY.
    IT NEVER RESOLVES, VERIFIES, SCORES, GRADES, RANKS, APPROVES, ONBOARDS,
    CONTACTS OR DECIDES.

    Since 0.2.0 it keeps those records in one tenant-bound local file (FD-13.2).
    That is persistence of the record and nothing more: what is stored is an
    opaque ``vendor_ref``, never an address, endpoint, credential, contract term
    or price, and the posture stays exactly as uninterpreted as before.

Contracts plus one ruled local file, under
``docs/architecture/ADR_UGENCE_VENDOR_RISK_SCOPING.md`` and front-door ruling FD-13.2:
record types, refusal reasons, pure selectors, one read-only Protocol and, since
0.2.0, ``SqliteVendorDeclarations`` — one tenant-bound, append-only sqlite file
implementing that Protocol plus the single append ``declare``. **No connector, no
gateway, no scorer, no clock, and no network** — nothing here could reach a vendor, a
policy, a model or a network, so the lines the rulings draw are held structurally
rather than by discipline. The file adds persistence and persistence only: no
taxonomy, no ordering, no comparison, no approval, no onboarding status.

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

A declaration is a record, not a permission. Storing one changes nothing about that.
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
    binding_from_dict,
    binding_to_dict,
    declaration_from_record,
    declaration_record,
    supersession_refusals,
    validity_from_dict,
    validity_to_dict,
)
from .durable import LEGACY_SCHEMA_VERSION, SCHEMA_VERSION, SqliteVendorDeclarations
from .errors import (
    ContractViolation,
    CrossTenantRefused,
    DeclarationProductionModeError,
    DeclarationStorageError,
    DeclarationSupersessionError,
    DuplicateDeclarationError,
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
from .vocabulary import (
    VocabularyBinding,
    VocabularyBindingState,
    vocabulary_binding_from_dict,
    vocabulary_binding_to_dict,
)
from .version import (
    CONTRACT_MATURITY,
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    MATURITY,
    __version__,
)

__all__ = [
    "__version__", "CONTRACT_VERSION", "LEGACY_CONTRACT_VERSION", "MATURITY", "CONTRACT_MATURITY", "ENFORCEMENT_ENABLED",
    # the system identity and the label, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus", "VendorRiskLabel",
    # the record
    "VendorDependencyDeclaration", "declaration_id_for", "DECLARATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    "binding_to_dict", "binding_from_dict", "declaration_record", "declaration_from_record",
    # the read seam and its pure selectors
    "VendorDependencyPort", "declared_at", "select_for_tenant", "select_for_vendor",
    "select_for_system", "select_by_risk_posture", "select_by_policy_ref",
    "supersession_chain",
    # the one ruled durable home (FD-13.2): declare is its only write (FD-13.4)
    "SqliteVendorDeclarations", "SCHEMA_VERSION", "LEGACY_SCHEMA_VERSION",
    # which published vocabulary the risk posture was written against (VV-A to VV-E)
    "VocabularyBinding", "VocabularyBindingState",
    "vocabulary_binding_to_dict", "vocabulary_binding_from_dict",
    # errors
    "VendorDependencyError", "ContractViolation", "DeclarationSupersessionError",
    "DeclarationStorageError", "DeclarationProductionModeError",
    "DuplicateDeclarationError", "CrossTenantRefused",
]
