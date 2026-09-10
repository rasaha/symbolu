"""Ugence AI System Registry — the contracts-only inventory of registered AI systems.

    THIS PACKAGE RECORDS WHAT AN ADMINISTRATOR ASSERTED.
    IT NEVER ADMITS, PROMOTES, APPROVES, GATES, RESOLVES OR ATTESTS.

Contracts only under the gap-sequencing ADR's decision D-5 for every module but one:
record types, refusal reasons, pure selectors and one read-only Protocol. Since 0.2.0,
front-door ruling FD-9.2 adds ``durable``, the one local sqlite store a composing
deployment owns (a file path; no server, driver, DSN or network), whose only write is
``register``. **No adapter, no connector, no admission engine** — the operational
registry and its systems-of-record connectors stay post-v1, and that line still holds
structurally because nothing here can reach one.

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

from .durable import LEGACY_SCHEMA_VERSION, SCHEMA_VERSION, SqliteSystemRegistry
from .errors import (
    AiSystemRegistryError,
    ContractViolation,
    CrossTenantRefused,
    DuplicateRegistrationError,
    RegistrationSupersessionError,
    RegistryProductionModeError,
    RegistryStorageError,
)
from .registration import (
    REGISTRATION_ID_PREFIX,
    SystemRegistration,
    binding_from_dict,
    binding_to_dict,
    registration_from_record,
    registration_id_for,
    registration_record,
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
    "__version__", "CONTRACT_VERSION", "LEGACY_CONTRACT_VERSION", "MATURITY",
    "CONTRACT_MATURITY", "ENFORCEMENT_ENABLED",
    # the system identity, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus",
    # the record
    "SystemRegistration", "registration_id_for", "REGISTRATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    "binding_to_dict", "binding_from_dict", "registration_record", "registration_from_record",
    # the one ruled local store (FD-9.2) and its refusals
    "SqliteSystemRegistry", "SCHEMA_VERSION", "LEGACY_SCHEMA_VERSION", "RegistryStorageError",
    # which published vocabulary the classification label was written against
    "VocabularyBinding", "VocabularyBindingState",
    "vocabulary_binding_to_dict", "vocabulary_binding_from_dict",
    "RegistryProductionModeError", "DuplicateRegistrationError", "CrossTenantRefused",
    # the read seam and its pure selectors
    "SystemRegistryPort", "registered_at", "select_for_tenant", "select_for_system",
    "select_by_classification", "supersession_chain",
    # errors
    "AiSystemRegistryError", "ContractViolation", "RegistrationSupersessionError",
]
