"""The PolicyPack aggregate and its lifecycle.

A :class:`PolicyPack` is the compiler's input and its versioned unit of review. It
holds typed collections of every policy-object category. Lifecycle transitions are
explicit, deterministic, and guarded: only an ``APPROVED`` pack may be compiled,
and illegal jumps (``DRAFT -> RELEASED``, ``REVIEW_REQUIRED -> COMPILED``,
``INVALID -> APPROVED``) are rejected.
"""

from __future__ import annotations

from typing import Dict, Iterator, Mapping, Tuple

from pydantic import Field

from .actions import ActionConstraint
from .approvals import HumanApprovalRecord
from .assurance import ReplayCase, TestScenario
from .audit import AuditRequirement
from .authority import ApprovalPath, ApprovalStep, AuthorityRequirement
from .common import (
    SCHEMA_VERSION,
    CompilerModel,
    ObjectType,
    PolicyObject,
    PolicyPackStatus,
)
from .connectors import ConnectorMapping
from .evidence import RequiredEvidence
from .exceptions import ExceptionRule
from .overrides import OverrideRule
from .provenance import SourceDocument
from .risks import LegitimateCounterexample, SequenceRiskPattern
from .rules import DecisionRule, ProhibitedCondition

#: Allowed lifecycle transitions. Anything not listed is rejected.
_ALLOWED_TRANSITIONS: Mapping[PolicyPackStatus, Tuple[PolicyPackStatus, ...]] = {
    PolicyPackStatus.DRAFT: (PolicyPackStatus.VALIDATING, PolicyPackStatus.SUPERSEDED),
    PolicyPackStatus.VALIDATING: (
        PolicyPackStatus.INVALID,
        PolicyPackStatus.REVIEW_REQUIRED,
        PolicyPackStatus.APPROVED,
        PolicyPackStatus.DRAFT,
    ),
    PolicyPackStatus.INVALID: (PolicyPackStatus.DRAFT, PolicyPackStatus.VALIDATING),
    PolicyPackStatus.REVIEW_REQUIRED: (
        PolicyPackStatus.APPROVED,
        PolicyPackStatus.DRAFT,
        PolicyPackStatus.VALIDATING,
    ),
    PolicyPackStatus.APPROVED: (
        PolicyPackStatus.COMPILED,
        PolicyPackStatus.SUPERSEDED,
        PolicyPackStatus.REVOKED,
    ),
    PolicyPackStatus.COMPILED: (
        PolicyPackStatus.RELEASED,
        PolicyPackStatus.SUPERSEDED,
        PolicyPackStatus.REVOKED,
    ),
    PolicyPackStatus.RELEASED: (PolicyPackStatus.SUPERSEDED, PolicyPackStatus.REVOKED),
    PolicyPackStatus.SUPERSEDED: (),
    PolicyPackStatus.REVOKED: (),
}


class IllegalLifecycleTransition(ValueError):
    """Raised when a policy-pack lifecycle transition is not permitted."""


def is_legal_transition(src: PolicyPackStatus, dst: PolicyPackStatus) -> bool:
    """Whether ``src -> dst`` is an allowed lifecycle transition."""
    return dst in _ALLOWED_TRANSITIONS.get(src, ())


class PolicyPack(CompilerModel):
    """A structured, reviewed governance policy pack — the compiler's input."""

    pack_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    schema_version: str = SCHEMA_VERSION
    status: PolicyPackStatus = PolicyPackStatus.DRAFT
    domain: str = ""
    description: str = ""

    source_documents: Tuple[SourceDocument, ...] = ()
    decision_rules: Tuple[DecisionRule, ...] = ()
    required_evidence: Tuple[RequiredEvidence, ...] = ()
    authority_requirements: Tuple[AuthorityRequirement, ...] = ()
    approval_paths: Tuple[ApprovalPath, ...] = ()
    approval_steps: Tuple[ApprovalStep, ...] = ()
    prohibited_conditions: Tuple[ProhibitedCondition, ...] = ()
    exception_rules: Tuple[ExceptionRule, ...] = ()
    override_rules: Tuple[OverrideRule, ...] = ()
    action_constraints: Tuple[ActionConstraint, ...] = ()
    sequence_risk_patterns: Tuple[SequenceRiskPattern, ...] = ()
    legitimate_counterexamples: Tuple[LegitimateCounterexample, ...] = ()
    connector_mappings: Tuple[ConnectorMapping, ...] = ()
    audit_requirements: Tuple[AuditRequirement, ...] = ()
    test_scenarios: Tuple[TestScenario, ...] = ()
    replay_cases: Tuple[ReplayCase, ...] = ()
    approval_records: Tuple[HumanApprovalRecord, ...] = ()

    # -- object access -------------------------------------------------------

    def all_objects(self) -> Iterator[PolicyObject]:
        """Yield every addressable :class:`PolicyObject` in the pack, in a
        deterministic collection order."""
        for collection in (
            self.source_documents,
            self.decision_rules,
            self.required_evidence,
            self.authority_requirements,
            self.approval_paths,
            self.approval_steps,
            self.prohibited_conditions,
            self.exception_rules,
            self.override_rules,
            self.action_constraints,
            self.sequence_risk_patterns,
            self.legitimate_counterexamples,
            self.connector_mappings,
            self.audit_requirements,
            self.test_scenarios,
            self.replay_cases,
            self.approval_records,
        ):
            yield from collection

    def object_index(self) -> Dict[str, PolicyObject]:
        """Map object_id -> object. Later duplicates overwrite earlier ones; the
        validator separately reports duplicate ids as an error."""
        return {obj.object_id: obj for obj in self.all_objects()}

    def objects_of_type(self, object_type: ObjectType) -> Tuple[PolicyObject, ...]:
        return tuple(o for o in self.all_objects() if o.object_type is object_type)

    # -- lifecycle -----------------------------------------------------------

    def with_status(self, new_status: PolicyPackStatus) -> "PolicyPack":
        """Return a copy transitioned to ``new_status``.

        Raises :class:`IllegalLifecycleTransition` if the transition is not
        permitted. Same-status is a no-op copy.
        """
        if new_status is self.status:
            return self
        if not is_legal_transition(self.status, new_status):
            raise IllegalLifecycleTransition(
                f"illegal transition {self.status.value} -> {new_status.value}"
            )
        return self.model_copy(update={"status": new_status})
