"""Phase 5E — frozen governance vocabulary, lifecycle, ports, hashes.

These are the controlled contracts. Each is pinned by a fingerprint (a
``canonical_hash`` over the exhaustive member/signature set) plus explicit
assertions on the headline enums. A change to any of them breaks a pin, forcing
an intentional, versioned decision (see ``decision_governance.version``: enum
*value* changes and lifecycle/serialization/hash/port changes are MAJOR;
appending members is MINOR and updates the pin deliberately).
"""

from __future__ import annotations

import inspect

from decision_governance import actions, decisions, execution
from decision_governance.audit import AuditEventType, AuditNamespace
from decision_governance.common import canonical_hash
from decision_governance.identity import ActorType
from decision_governance.policy import Permission
from decision_governance.vocabulary import ReasonCode, UncertaintyLevel
from decision_governance.actions.control_plane import ActionControlPlanePort
from decision_governance.execution.external_system import ExternalExecutionPort
from decision_governance.ports.linked_record import LinkedRecordPort

# --- pinned fingerprints ----------------------------------------------------
VOCAB_FINGERPRINT = "7273232a94c8b62a11ee0d44f0e674a11463770f09676cc1f4535c12dd18ac91"
LIFECYCLE_FINGERPRINT = "febe54cf97b3f133db8459fc8effd9aa6de2856c88f4d61fdc1e14bc4e56c9a6"
PORT_FINGERPRINT = "d3d7ae7029067e52fe1546c1834fb024ecd1df279ff2d6c392ea3c1fcbc05494"

_CONTROLLED_ENUMS = {
    "DecisionOutcome": decisions.DecisionOutcome,
    "ProposedOutcome": decisions.ProposedOutcome,
    "AuthorityType": decisions.AuthorityType,
    "GeneratorType": decisions.GeneratorType,
    "CaseStatus": decisions.CaseStatus,
    "RecommendationStatus": decisions.RecommendationStatus,
    "EffectiveStatus": decisions.EffectiveStatus,
    "ReviewTaskType": decisions.ReviewTaskType,
    "ReviewTaskStatus": decisions.ReviewTaskStatus,
    "OperatingMode": decisions.OperatingMode,
    "ActionRequestStatus": actions.ActionRequestStatus,
    "AuthorizationOutcome": actions.AuthorizationOutcome,
    "ActionMappingStatus": actions.ActionMappingStatus,
    "ExecutionStatus": execution.ExecutionStatus,
    "TransportStatus": execution.TransportStatus,
    "BusinessOutcome": execution.BusinessOutcome,
    "ReconciliationStatus": execution.ReconciliationStatus,
    "RetryClassification": execution.RetryClassification,
    "CompensationType": execution.CompensationType,
    "CompensationApprovalStatus": execution.CompensationApprovalStatus,
    "Finality": execution.Finality,
    "OutcomeSource": execution.OutcomeSource,
    "Permission": Permission,
    "ActorType": ActorType,
    "AuditNamespace": AuditNamespace,
    "ReasonCode": ReasonCode,
    "UncertaintyLevel": UncertaintyLevel,
    "AuditEventType": AuditEventType,
}


def test_controlled_vocabulary_fingerprint_is_frozen():
    vocab = {name: sorted((m.name, m.value) for m in enum)
             for name, enum in _CONTROLLED_ENUMS.items()}
    assert canonical_hash(vocab) == VOCAB_FINGERPRINT


def test_headline_enum_members_are_exact():
    assert [m.value for m in decisions.DecisionOutcome] == [
        "ADVANCE", "HOLD", "REJECT", "DEFER"]
    assert [m.value for m in decisions.AuthorityType] == [
        "HUMAN_REVIEWER", "HUMAN_APPROVER", "DELEGATED_POLICY", "COMMITTEE",
        "EXTERNAL_AUTHORITY"]
    assert [m.value for m in execution.ReconciliationStatus] == [
        "RECONCILED", "MISMATCHED", "PARTIALLY_RECONCILED", "INDETERMINATE",
        "MANUAL_REVIEW_REQUIRED", "COMPENSATION_REQUIRED"]
    assert [m.value for m in AuditNamespace] == ["KERNEL", "LEGACY", "DOMAIN"]


def test_audit_catalog_is_frozen():
    # Every event name equals its value (no renames), and the catalog size is pinned.
    assert all(m.name == m.value for m in AuditEventType)
    assert len(list(AuditEventType)) == 110


def test_lifecycle_transitions_are_frozen():
    lifecycle = {
        "decisions": sorted((str(k), sorted(str(v) for v in vs))
                            for k, vs in decisions.ALLOWED_TRANSITIONS.items()),
        "actions": sorted((str(k), sorted(str(v) for v in vs))
                          for k, vs in actions.ALLOWED_TRANSITIONS.items()),
        "execution": sorted((str(k), sorted(str(v) for v in vs))
                            for k, vs in execution.ALLOWED_TRANSITIONS.items()),
    }
    assert canonical_hash(lifecycle) == LIFECYCLE_FINGERPRINT


def test_port_signatures_are_frozen():
    ports = {
        p.__name__: sorted(
            f"{n}{inspect.signature(getattr(p, n))}"
            for n in dir(p)
            if not n.startswith("_") and callable(getattr(p, n)))
        for p in (LinkedRecordPort, ActionControlPlanePort, ExternalExecutionPort)
    }
    assert canonical_hash(ports) == PORT_FINGERPRINT


def test_repository_and_service_interfaces_present():
    from decision_governance.repositories import (
        DecisionCaseRepository, ActionRequestRepository, ExecutionRepository)
    for repo, methods in (
        (DecisionCaseRepository, ("get_case", "save_case_version")),
        (ActionRequestRepository, ("get_action_request",)),
        (ExecutionRepository, ("get_execution_intent",)),
    ):
        for m in methods:
            assert hasattr(repo, m), f"{repo.__name__}.{m}"
    from decision_governance.services import DecisionCaseService, ExecutionService
    assert hasattr(DecisionCaseService, "create_case")
    assert hasattr(ExecutionService, "dispatch_execution")


def test_serialization_is_stable_round_trip():
    from decision_governance.ports.linked_record import LinkedRecordSnapshot
    snap = LinkedRecordSnapshot(
        record_type="assessment", record_id="a1", version=1, tenant_id="t",
        status="FINALIZED", subject_ref="s1")
    dumped = snap.model_dump()
    restored = LinkedRecordSnapshot(**dumped)
    assert restored == snap
    assert restored.model_dump() == dumped
