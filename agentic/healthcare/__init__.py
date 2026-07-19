"""
Healthcare data-access governance — a self-contained domain specialization of
the generic ActionGate (agentic.agentic_framework governance stack).

This package governs WHAT hospital AI agents and staff-facing automations may
read, summarize, redact, disclose, or export. It is NOT a diagnosis, treatment,
or autonomous clinical system. It is an authorization / policy-enforcement
boundary.

Architecture boundary
---------------------
The generic engine is used UNCHANGED. This package supplies only domain
configuration and adaptation:

  * taxonomy.py   — configurable healthcare enums (operations/roles/categories/
                    purposes/consent).
  * request.py    — HealthcareAccessRequest (classifications & references, not
                    raw PHI).
  * criticality.py— deterministic criticality derivation + minimum-necessary
                    permitted-category map (never trusts caller-declared risk).
  * policy.py     — healthcare HumanPolicyBook fixtures, ActionCriticalityRegistry,
                    and the forbidden-capability PolicyResolution used to route
                    healthcare hard blocks through the generic hard-block layer.
  * service.py    — HealthcareGovernanceService: adapt → generic authorize →
                    minimum-necessary + applicability enrichment → PHI-safe audit.

No hospital rule lives inside GovernanceService or HumanPolicyEngine.
"""

from agentic.healthcare.taxonomy import (
    ConsentState,
    DataCategory,
    DestinationClass,
    Operation,
    Purpose,
    RecipientType,
    Role,
    RESTRICTED_CATEGORIES,
    PROHIBITED_CATEGORIES,
    DIRECT_IDENTIFIER_CATEGORIES,
)
from agentic.healthcare.request import HealthcareAccessRequest
from agentic.healthcare.criticality import (
    CriticalityDerivation,
    derive_criticality,
    minimum_necessary_categories,
)
from agentic.healthcare.policy import (
    HEALTHCARE_HARD_BLOCK_CAPABILITIES,
    build_healthcare_policy_book,
    build_healthcare_criticality_registry,
    build_healthcare_forbidden_policy_resolution,
)
from agentic.healthcare.service import (
    HealthcareGovernanceService,
    HealthcareAccessDecision,
)

__all__ = [
    "ConsentState",
    "DataCategory",
    "DestinationClass",
    "Operation",
    "Purpose",
    "RecipientType",
    "Role",
    "RESTRICTED_CATEGORIES",
    "PROHIBITED_CATEGORIES",
    "DIRECT_IDENTIFIER_CATEGORIES",
    "HealthcareAccessRequest",
    "CriticalityDerivation",
    "derive_criticality",
    "minimum_necessary_categories",
    "HEALTHCARE_HARD_BLOCK_CAPABILITIES",
    "build_healthcare_policy_book",
    "build_healthcare_criticality_registry",
    "build_healthcare_forbidden_policy_resolution",
    "HealthcareGovernanceService",
    "HealthcareAccessDecision",
]
