"""Ugence AI System Registry — the contracts-only inventory of registered AI systems.

    THIS PACKAGE RECORDS WHAT AN ADMINISTRATOR ASSERTED.
    IT NEVER ADMITS, PROMOTES, APPROVES, GATES, RESOLVES OR ATTESTS.

Contracts only under the gap-sequencing ADR's decision D-5: record types, refusal
reasons, pure selectors and one read-only Protocol. **No store, no adapter, no
connector, no admission engine** — the operational registry and its systems-of-record
connectors stay post-v1, and the line holds structurally because nothing here could
cross it.

It is not a portfolio ledger: ``WorkflowPortfolio`` in ``packages/runtime/agent-runtime``
remains the only one. It mints no system identity: ``AssessedSystemBinding`` is
re-exported from governance-contracts, never redefined.

Scoped and ratified by ``docs/architecture/ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md``.
A registration is a record, not a permission.
"""

from __future__ import annotations

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    SystemBindingAuthenticityStatus,
)

from .errors import (
    AiSystemRegistryError,
    ContractViolation,
    RegistrationSupersessionError,
)
from .registration import (
    REGISTRATION_ID_PREFIX,
    SystemRegistration,
    registration_id_for,
    require_admissible_supersession,
    supersession_refusals,
    validity_from_dict,
    validity_to_dict,
)
from .registry import (
    SystemRegistryPort,
    registered_at,
    select_by_classification,
    select_for_system,
    select_for_tenant,
    supersession_chain,
)
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # the system identity, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus",
    # the record
    "SystemRegistration", "registration_id_for", "REGISTRATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    # the read seam and its pure selectors
    "SystemRegistryPort", "registered_at", "select_for_tenant", "select_for_system",
    "select_by_classification", "supersession_chain",
    # errors
    "AiSystemRegistryError", "ContractViolation", "RegistrationSupersessionError",
]
