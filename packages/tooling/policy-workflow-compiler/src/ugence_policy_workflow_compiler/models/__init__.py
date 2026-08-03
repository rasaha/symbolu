"""Structured policy-pack object model.

Typed, versioned, provenance-aware declarative objects. Import concrete objects
from here; the curated public API re-exports the stable subset from
:mod:`ugence_policy_workflow_compiler.api`.
"""

from __future__ import annotations

from .actions import ActionConstraint, ConstraintKind
from .approvals import ApprovalDecision, HumanApprovalRecord
from .assurance import (
    REQUIRED_TEST_CATEGORIES,
    AssuranceManifest,
    CoverageMatrix,
    ExpectedOutcome,
    ReplayCase,
    TestCategory,
    TestScenario,
)
from .audit import (
    BASELINE_AUDIT_FIELDS,
    AuditFieldDefinition,
    AuditRequirement,
    AuditSchema,
)
from .authority import ApprovalPath, ApprovalStep, AuthorityRequirement
from .common import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    AuthorityDisposition,
    AuthorityType,
    BlockBehavior,
    CapabilityId,
    CompilerModel,
    ObjectType,
    PolicyObject,
    PolicyPackStatus,
    ProvenanceStatus,
)
from .connectors import ConnectorMapping
from .evidence import EvidenceKind, RequiredEvidence
from .exceptions import ExceptionRule
from .overrides import OverrideRule
from .policy_pack import (
    IllegalLifecycleTransition,
    PolicyPack,
    is_legal_transition,
)
from .provenance import ProvenanceReference, ProvenanceSourceType, SourceDocument
from .risks import LegitimateCounterexample, SequenceRiskPattern
from .rules import Comparator, DecisionRule, Predicate, ProhibitedCondition

__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "AuthorityDisposition",
    "AuthorityType",
    "BlockBehavior",
    "CapabilityId",
    "CompilerModel",
    "ObjectType",
    "PolicyObject",
    "PolicyPackStatus",
    "ProvenanceStatus",
    "ProvenanceReference",
    "ProvenanceSourceType",
    "SourceDocument",
    "Comparator",
    "Predicate",
    "DecisionRule",
    "ProhibitedCondition",
    "EvidenceKind",
    "RequiredEvidence",
    "AuthorityRequirement",
    "ApprovalPath",
    "ApprovalStep",
    "ExceptionRule",
    "OverrideRule",
    "ActionConstraint",
    "ConstraintKind",
    "SequenceRiskPattern",
    "LegitimateCounterexample",
    "ConnectorMapping",
    "TestCategory",
    "REQUIRED_TEST_CATEGORIES",
    "TestScenario",
    "ReplayCase",
    "ExpectedOutcome",
    "CoverageMatrix",
    "AssuranceManifest",
    "AuditRequirement",
    "AuditFieldDefinition",
    "AuditSchema",
    "BASELINE_AUDIT_FIELDS",
    "ApprovalDecision",
    "HumanApprovalRecord",
    "PolicyPack",
    "is_legal_transition",
    "IllegalLifecycleTransition",
]
