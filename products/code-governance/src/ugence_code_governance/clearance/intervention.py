"""Deterministic, explainable human-intervention assessment and routing.

This is **advisory/routing metadata**, not a binding decision — it never replaces
Decision Authority and is never a ``DecisionRecord``. It is **non-compensatory**:
no positive signal offsets a failed mandatory binding condition, and every
load-bearing reason is preserved. There is **no blended risk/intervention score**.

Not every non-CLEAR status requires human intervention. By default only ESCALATE
(and policy-configured exception/critical routes) require a human; HOLD means
wait/refresh and BLOCK means change/reauthorize.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple

from ugence_action_clearance import ClearanceStatus  # type: ignore

from ..fingerprints import domain_hash
from .profile import CodeGovernanceClearanceProfile, RepositoryClassification


class InterventionType(str, Enum):
    """Curated product intervention vocabulary (no free-form LLM types)."""

    NONE = "NONE"
    WAIT_FOR_CONDITION = "WAIT_FOR_CONDITION"
    REFRESH_SIGNAL = "REFRESH_SIGNAL"
    REAUTHORIZE_CHANGE = "REAUTHORIZE_CHANGE"
    CODE_OWNER_REVIEW = "CODE_OWNER_REVIEW"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    OPERATIONS_REVIEW = "OPERATIONS_REVIEW"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    EXCEPTION_APPROVAL = "EXCEPTION_APPROVAL"
    BINDING_AUTHORITY_DECISION = "BINDING_AUTHORITY_DECISION"


class AuthorityRole(str, Enum):
    """Curated authority roles a routing rule may require."""

    CODE_OWNER = "CODE_OWNER"
    SECURITY_REVIEWER = "SECURITY_REVIEWER"
    OPERATIONS = "OPERATIONS"
    INCIDENT_COMMANDER = "INCIDENT_COMMANDER"
    SERVICE_OWNER = "SERVICE_OWNER"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    RELEASE_MANAGER = "RELEASE_MANAGER"


@dataclass(frozen=True)
class RouteEntry:
    """The deterministic routing outcome for one clearance reason."""

    intervention_required: bool
    intervention_type: InterventionType
    required_authorities: Tuple[AuthorityRole, ...]
    blocking: bool
    recommended_next_action: str


# --- default neutral routing table (reason_code -> RouteEntry) -------------
_WAIT = InterventionType.WAIT_FOR_CONDITION
_REFRESH = InterventionType.REFRESH_SIGNAL
_REAUTH = InterventionType.REAUTHORIZE_CHANGE
_NONE = InterventionType.NONE

# reason -> (type, human_required, authorities, blocking, next_action)
_DEFAULT_ROUTES: Mapping[str, RouteEntry] = {
    "CLEARANCE_GRANTED": RouteEntry(False, _NONE, (), False, "proceed (shadow only; execution disabled)"),
    # HOLD — wait / refresh, no human by default
    "ACTIVE_CHANGE_FREEZE": RouteEntry(False, _WAIT, (), False, "wait for change freeze to lift"),
    "TARGET_UNAVAILABLE": RouteEntry(False, _WAIT, (), False, "retry when target is available"),
    "CONSUMPTION_RESERVED": RouteEntry(False, _WAIT, (), False, "wait for reservation to resolve"),
    "SIGNAL_MISSING": RouteEntry(False, _REFRESH, (), False, "supply the missing operational signal"),
    "SIGNAL_STALE": RouteEntry(False, _REFRESH, (), False, "refresh the stale operational signal"),
    "SIGNAL_EXPIRED": RouteEntry(False, _REFRESH, (), False, "refresh the expired operational signal"),
    "ACTOR_STATUS_UNKNOWN": RouteEntry(False, _REFRESH, (), False, "refresh the actor-status signal"),
    "CONSUMPTION_STATUS_UNKNOWN": RouteEntry(False, _REFRESH, (), False, "refresh the consumption signal"),
    "AUTHORIZATION_STALE": RouteEntry(False, _REFRESH, (), False, "refresh authorization-validity or re-authorize"),
    # BLOCK — change / reauthorize, no automatic human by default
    "AUTHORIZATION_EXPIRED": RouteEntry(False, _REAUTH, (), True, "re-authorize the change upstream"),
    "AUTHORIZATION_NOT_ELIGIBLE": RouteEntry(False, _REAUTH, (), True, "re-authorize; ActionGate did not authorize"),
    "ACTION_FINGERPRINT_MISMATCH": RouteEntry(False, _REAUTH, (), True, "new authorization + clearance for the exact action"),
    "TARGET_MISMATCH": RouteEntry(False, _REAUTH, (), True, "correct target; re-authorize"),
    "TENANT_MISMATCH": RouteEntry(False, _REAUTH, (), True, "fix tenant binding; re-authorize"),
    "SUBJECT_MISMATCH": RouteEntry(False, _REAUTH, (), True, "fix subject binding; re-authorize"),
    "POLICY_VERSION_REJECTED": RouteEntry(False, _REAUTH, (), True, "re-authorize under the current policy version"),
    "ACTOR_INVALID": RouteEntry(False, _REAUTH, (), True, "restore actor or re-authorize"),
    "REQUIRED_CONTROL_UNSATISFIED": RouteEntry(False, _REAUTH, (), True, "satisfy the required control; re-authorize"),
    "ALREADY_CONSUMED": RouteEntry(False, _NONE, (), True, "none — the authorization was already consumed"),
    "SIGNAL_UNTRUSTED": RouteEntry(False, _REFRESH, (), True, "fix signal provenance/integrity and re-supply"),
    "SIGNAL_PROVENANCE_MISSING": RouteEntry(False, _REFRESH, (), True, "attach signal provenance and re-supply"),
    "SIGNAL_SOURCE_UNAPPROVED": RouteEntry(False, _REFRESH, (), True, "use an approved signal source"),
    "SIGNAL_ADAPTER_VERSION_UNAPPROVED": RouteEntry(False, _REFRESH, (), True, "use an approved adapter version"),
    "SIGNAL_TRUST_LEVEL_INSUFFICIENT": RouteEntry(False, _REFRESH, (), True, "supply a higher-trust signal"),
    "SIGNAL_CONTENT_MISMATCH": RouteEntry(False, _REFRESH, (), True, "re-supply the signal with a valid content digest"),
    "SIGNAL_AUTHORIZATION_MISMATCH": RouteEntry(False, _REAUTH, (), True, "bind the signal to the correct authorization"),
    "SIGNAL_ACTION_MISMATCH": RouteEntry(False, _REAUTH, (), True, "bind the signal to the exact action"),
    # ESCALATE — human required
    "SIGNAL_CONFLICT": RouteEntry(True, InterventionType.OPERATIONS_REVIEW,
                                  (AuthorityRole.OPERATIONS,), False, "human resolves conflicting signals"),
    "CONSTRAINT_CONFLICT": RouteEntry(True, InterventionType.EXCEPTION_APPROVAL,
                                      (AuthorityRole.RELEASE_MANAGER,), True,
                                      "cannot widen authorization; exception approval or re-authorize"),
    "CONSTRAINT_INTERPRETATION_UNSUPPORTED": RouteEntry(True, InterventionType.OPERATIONS_REVIEW,
                                                        (AuthorityRole.OPERATIONS,), True,
                                                        "human resolves uninterpretable constraint"),
    "CLEARANCE_POLICY_CONFLICT": RouteEntry(True, InterventionType.OPERATIONS_REVIEW,
                                            (AuthorityRole.OPERATIONS,), True,
                                            "human resolves policy conflict"),
}

# Incident routing depends on repository classification.
_INCIDENT_CRITICAL = RouteEntry(True, InterventionType.OPERATIONS_REVIEW,
                                (AuthorityRole.INCIDENT_COMMANDER, AuthorityRole.SERVICE_OWNER),
                                False, "incident commander / service owner decision")
_INCIDENT_DEFAULT = RouteEntry(False, _WAIT, (), False, "wait for the incident to clear")


@dataclass(frozen=True)
class InterventionRoutingPolicy:
    """Immutable deterministic routing from clearance reasons to human authority."""

    routing_id: str = "default-routing"
    routing_version: str = "v1"
    #: Per-reason overrides (reason_code -> RouteEntry).
    overrides: Mapping[str, RouteEntry] = field(default_factory=dict)
    #: Reason codes routed to SECURITY_REVIEW when the component is sensitive.
    security_sensitive_reasons: Tuple[str, ...] = ("SIGNAL_CONFLICT",)

    def route(
        self,
        reason_code: str,
        *,
        classification: RepositoryClassification,
        sensitive: bool,
    ) -> RouteEntry:
        if reason_code in self.overrides:
            return self.overrides[reason_code]
        if reason_code == "ACTIVE_INCIDENT":
            return (_INCIDENT_CRITICAL
                    if classification is RepositoryClassification.CRITICAL else _INCIDENT_DEFAULT)
        base = _DEFAULT_ROUTES.get(reason_code)
        if base is None:
            # Unknown reason -> fail closed to operations review (deterministic).
            return RouteEntry(True, InterventionType.OPERATIONS_REVIEW,
                              (AuthorityRole.OPERATIONS,), True,
                              f"human review for unrouted reason {reason_code}")
        if sensitive and reason_code in self.security_sensitive_reasons:
            return RouteEntry(True, InterventionType.SECURITY_REVIEW,
                              (AuthorityRole.SECURITY_REVIEWER,), base.blocking,
                              "security review for a sensitive component")
        return base

    @property
    def policy_ref(self) -> str:
        return f"{self.routing_id}:{self.routing_version}"


@dataclass(frozen=True)
class HumanInterventionAssessment:
    """Deterministic, explainable, non-binding intervention assessment."""

    assessment_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    clearance_status: str
    required: bool
    blocking: bool
    intervention_types: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    source_stage: str
    required_authorities: Tuple[str, ...]
    signal_refs: Tuple[str, ...]
    claim_refs: Tuple[str, ...]
    policy_refs: Tuple[str, ...]
    recommended_next_actions: Tuple[str, ...]

    #: This is never a binding decision.
    is_binding: bool = field(default=False, init=False)

    @property
    def fingerprint(self) -> str:
        return domain_hash("human_intervention_assessment.v1", {
            "tenant_id": self.tenant_id,
            "workflow_revision_id": self.workflow_revision_id,
            "clearance_status": self.clearance_status,
            "required": self.required,
            "blocking": self.blocking,
            "intervention_types": sorted(self.intervention_types),
            "reason_codes": sorted(self.reason_codes),
            "required_authorities": sorted(self.required_authorities),
            "signal_refs": sorted(self.signal_refs),
            "policy_refs": sorted(self.policy_refs),
            "recommended_next_actions": list(self.recommended_next_actions),
        })


def assess_intervention(
    *,
    tenant_id: str,
    workflow_id: str,
    workflow_revision_id: str,
    clearance_status: ClearanceStatus,
    reason_codes: Tuple[str, ...],
    signal_refs: Tuple[str, ...],
    profile: CodeGovernanceClearanceProfile,
    routing: InterventionRoutingPolicy,
    claim_refs: Tuple[str, ...] = (),
    sensitive: bool = False,
    source_stage: str = "CLEARANCE_EVALUATED",
) -> HumanInterventionAssessment:
    """Deterministically route clearance reasons to an intervention assessment.

    Non-compensatory: every reason is routed independently; the union of routes is
    reported. No aggregate score is computed.
    """
    classification = profile.repository_classification
    types: set = set()
    authorities: set = set()
    next_actions: list = []
    required = False
    blocking = False

    routed_reasons = list(reason_codes)
    # A CLEAR result with no load-bearing reason: honor automatic-continuation policy.
    if clearance_status is ClearanceStatus.CLEAR and (
        not routed_reasons or routed_reasons == ["CLEARANCE_GRANTED"]
    ):
        if profile.automatic_continuation_eligible:
            return HumanInterventionAssessment(
                assessment_id=_assessment_id(workflow_revision_id, clearance_status, reason_codes),
                tenant_id=tenant_id, workflow_id=workflow_id,
                workflow_revision_id=workflow_revision_id,
                clearance_status=clearance_status.value, required=False, blocking=False,
                intervention_types=(InterventionType.NONE.value,), reason_codes=tuple(reason_codes),
                source_stage=source_stage, required_authorities=(), signal_refs=tuple(signal_refs),
                claim_refs=tuple(claim_refs), policy_refs=(profile.policy_ref, routing.policy_ref),
                recommended_next_actions=("proceed (shadow only; execution disabled)",))
        # policy independently requires manual review for this change class
        return HumanInterventionAssessment(
            assessment_id=_assessment_id(workflow_revision_id, clearance_status, reason_codes),
            tenant_id=tenant_id, workflow_id=workflow_id,
            workflow_revision_id=workflow_revision_id,
            clearance_status=clearance_status.value, required=True, blocking=False,
            intervention_types=(InterventionType.CODE_OWNER_REVIEW.value,),
            reason_codes=tuple(reason_codes), source_stage=source_stage,
            required_authorities=(AuthorityRole.CODE_OWNER.value,), signal_refs=tuple(signal_refs),
            claim_refs=tuple(claim_refs), policy_refs=(profile.policy_ref, routing.policy_ref),
            recommended_next_actions=("company policy requires manual review for this change class",))

    for rc in routed_reasons:
        if rc == "CLEARANCE_GRANTED":
            continue
        entry = routing.route(rc, classification=classification, sensitive=sensitive)
        types.add(entry.intervention_type.value)
        for a in entry.required_authorities:
            authorities.add(a.value)
        if entry.recommended_next_action not in next_actions:
            next_actions.append(entry.recommended_next_action)
        required = required or entry.intervention_required
        blocking = blocking or entry.blocking
    if not types:
        types.add(InterventionType.NONE.value)

    return HumanInterventionAssessment(
        assessment_id=_assessment_id(workflow_revision_id, clearance_status, reason_codes),
        tenant_id=tenant_id, workflow_id=workflow_id,
        workflow_revision_id=workflow_revision_id,
        clearance_status=clearance_status.value, required=required, blocking=blocking,
        intervention_types=tuple(sorted(types)), reason_codes=tuple(reason_codes),
        source_stage=source_stage, required_authorities=tuple(sorted(authorities)),
        signal_refs=tuple(signal_refs), claim_refs=tuple(claim_refs),
        policy_refs=(profile.policy_ref, routing.policy_ref),
        recommended_next_actions=tuple(next_actions))


def _assessment_id(revision_id: str, status: ClearanceStatus, reason_codes) -> str:
    return "hia_" + domain_hash("human_intervention_id.v1", {
        "revision_id": revision_id, "status": status.value,
        "reason_codes": sorted(reason_codes)})


__all__ = [
    "InterventionType",
    "AuthorityRole",
    "RouteEntry",
    "InterventionRoutingPolicy",
    "HumanInterventionAssessment",
    "assess_intervention",
]
