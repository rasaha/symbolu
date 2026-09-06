"""Ugence Data-Use Admission — the record of declared data use, and its one local home.

    THIS PACKAGE RECORDS WHAT A DECLARER ASSERTED ABOUT DATA.
    IT NEVER INSPECTS, CLASSIFIES, REDACTS, MINIMIZES, ADMITS,
    AUTHORIZES, SELECTS, ENFORCES OR GOVERNS EGRESS.

    Since 0.2.0 it keeps those records in one tenant-bound local file (FD-12.2). That
    is persistence of the record and nothing more: what is stored is the reference,
    never the data, and the labels stay exactly as uninterpreted as before.

Contracts plus one ruled local file, under
``docs/architecture/ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md`` and front-door ruling
FD-12.2: record types, refusal reasons, pure selectors, one read-only Protocol and,
since 0.2.0, ``SqliteDataUseDeclarations`` — one tenant-bound, append-only sqlite file
implementing that Protocol plus the single append ``declare``. **No adapter, no
connector, no proxy, no redactor, no clock, and no network** — nothing here can reach
data, a context, a model or a system of record, so the lines the rulings draw are still
held structurally rather than by discipline. The file adds persistence and persistence
only: no taxonomy, no ordering, no comparison, no admission.

* DE-1 ``ADMISSION_ONLY`` — a declaration describes data at the seam *before* it
  enters a governed context (``packages/capabilities/context-minimization/README.md:14``).
  Result and output egress is deferred and absent here.
* DE-2 ``STAY_SPLIT`` — residency is recorded as metadata and never evaluated;
  ActionGate's ``allowed_region`` and Model Selection's ``data_residency_allowed``
  keep their own questions, and neither is imported.
* DE-3 ``UNINTERPRETED`` — the label is what the declarer called the data; there is
  no taxonomy, ordering or compatibility anywhere.
* DE-5 — ``DataClassificationLabel`` and ``AssessedSystemBinding`` are re-exported
  from governance-contracts, never redefined.

A declaration is a record, not a permission. Storing one changes nothing about that.
"""

from __future__ import annotations

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    DataClassificationLabel,
    SystemBindingAuthenticityStatus,
)

from .declaration import (
    DECLARATION_ID_PREFIX,
    DataUseDeclaration,
    binding_from_dict,
    binding_to_dict,
    declaration_from_record,
    declaration_id_for,
    declaration_record,
    require_admissible_supersession,
    supersession_refusals,
    validity_from_dict,
    validity_to_dict,
)
from .durable import SCHEMA_VERSION, SqliteDataUseDeclarations
from .errors import (
    ContractViolation,
    CrossTenantRefused,
    DataUseAdmissionError,
    DeclarationProductionModeError,
    DeclarationStorageError,
    DeclarationSupersessionError,
    DuplicateDeclarationError,
)
from .selectors import (
    DataUseDeclarationPort,
    declared_at,
    select_by_classification,
    select_by_purpose,
    select_for_data,
    select_for_system,
    select_for_tenant,
    supersession_chain,
)
from .version import (
    CONTRACT_MATURITY,
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    MATURITY,
    __version__,
)

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "CONTRACT_MATURITY", "ENFORCEMENT_ENABLED",
    # the system identity and the label, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus", "DataClassificationLabel",
    # the record
    "DataUseDeclaration", "declaration_id_for", "DECLARATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    "binding_to_dict", "binding_from_dict", "declaration_record", "declaration_from_record",
    # the read seam and its pure selectors
    "DataUseDeclarationPort", "declared_at", "select_for_tenant", "select_for_data",
    "select_for_system", "select_by_classification", "select_by_purpose",
    "supersession_chain",
    # the one ruled durable home (FD-12.2): declare is its only write (FD-12.5)
    "SqliteDataUseDeclarations", "SCHEMA_VERSION",
    # errors
    "DataUseAdmissionError", "ContractViolation", "DeclarationSupersessionError",
    "DeclarationStorageError", "DeclarationProductionModeError",
    "DuplicateDeclarationError", "CrossTenantRefused",
]
