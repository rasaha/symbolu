"""Ugence Data-Use Admission — the contracts-only record of declared data use.

    THIS PACKAGE RECORDS WHAT A DECLARER ASSERTED ABOUT DATA.
    IT NEVER INSPECTS, CLASSIFIES, REDACTS, MINIMIZES, PERSISTS, ADMITS,
    AUTHORIZES, SELECTS, ENFORCES OR GOVERNS EGRESS.

Contracts only, under ``docs/architecture/ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md``:
record types, refusal reasons, pure selectors and one read-only Protocol. **No
store, no adapter, no connector, no proxy, no redactor, no clock** — nothing here
could reach data, a context, a model or a network, so the lines the rulings draw
are held structurally rather than by discipline.

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

A declaration is a record, not a permission.
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
    declaration_id_for,
    require_admissible_supersession,
    supersession_refusals,
    validity_from_dict,
    validity_to_dict,
)
from .errors import (
    ContractViolation,
    DataUseAdmissionError,
    DeclarationSupersessionError,
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
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # the system identity and the label, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus", "DataClassificationLabel",
    # the record
    "DataUseDeclaration", "declaration_id_for", "DECLARATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    # the read seam and its pure selectors
    "DataUseDeclarationPort", "declared_at", "select_for_tenant", "select_for_data",
    "select_for_system", "select_by_classification", "select_by_purpose",
    "supersession_chain",
    # errors
    "DataUseAdmissionError", "ContractViolation", "DeclarationSupersessionError",
]
