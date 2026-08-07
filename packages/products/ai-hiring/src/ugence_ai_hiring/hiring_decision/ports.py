"""Integration ports to shared Ugence governance capabilities.

These are **interfaces only**. This package does not implement Decision
Authority, ActionGate, Runtime Assurance / ACP, TAP, or Reconciliation — those
are shared platform services reached through these ports and their adapters. The
package runs standalone by injecting test adapters/mocks (see the package tests);
nothing here imports the platform, so import never requires the full stack.

DTOs are neutral value objects; adapters translate them to/from each capability's
native contract.
"""

from __future__ import annotations

from typing import Literal, Optional, Protocol, runtime_checkable

from pydantic import Field

from ..domain.base import DomainModel
from ..hiring_policy.enums import HiringEvidenceClass, RuntimeAssuranceCheck
from .enums import (
    ActionAuthorizationVerdict,
    AssuranceResult,
    DecisionDisposition,
    Trajectory,
)
from .refs import ContractRef


# --- EvidenceAdmissionPort → TAP -----------------------------------------
class EvidenceSubmission(DomainModel):
    evidence_id: str
    evidence_class: HiringEvidenceClass
    candidate_id: str
    role_id: str
    payload_ref: str


class AdmissionOutcome(DomainModel):
    evidence_id: str
    admitted: bool
    lineage_node_id: str
    reason: str = ""


@runtime_checkable
class EvidenceAdmissionPort(Protocol):
    """Admits (or rejects) evidence via the shared Truth Assurance Pipeline."""

    def admit(self, submissions: tuple[EvidenceSubmission, ...]) -> tuple[AdmissionOutcome, ...]: ...


# --- DecisionAuthorityPort ------------------------------------------------
class DecisionAuthorityOutcome(DomainModel):
    """The shared Decision Authority's adjudication of an advisory recommendation.

    This is the *only* way an advisory recommendation becomes binding, and only a
    HUMAN authority may bind (``actor_type`` is pinned to HUMAN).
    """

    recommendation_id: str
    disposition: DecisionDisposition
    binding: bool
    authority_id: str
    actor_type: Literal["HUMAN"] = "HUMAN"
    rationale_job_related: str = ""
    override_reason: Optional[str] = None


@runtime_checkable
class DecisionAuthorityPort(Protocol):
    """Submits an advisory recommendation to the shared Decision Authority."""

    def adjudicate(
        self, recommendation_id: str, contract_ref: ContractRef
    ) -> DecisionAuthorityOutcome: ...


# --- ActionAuthorizationPort → ActionGate --------------------------------
class ActionAuthorizationOutcome(DomainModel):
    verdict: ActionAuthorizationVerdict
    reason: str = ""
    constraints: tuple[str, ...] = ()


@runtime_checkable
class ActionAuthorizationPort(Protocol):
    """Authorizes a hiring action against the shared ActionGate.

    Accepts the neutral CER payload produced by
    :meth:`HiringActionRequest.to_cer_payload`.
    """

    def authorize(self, cer_payload: dict) -> ActionAuthorizationOutcome: ...


# --- RuntimeAssurancePort → Runtime Assurance / ACP ----------------------
class AssuranceCheckResult(DomainModel):
    check: RuntimeAssuranceCheck
    passed: bool
    detail: str = ""


class AssuranceOutcome(DomainModel):
    result: AssuranceResult
    check_results: tuple[AssuranceCheckResult, ...] = ()

    def failed_checks(self) -> tuple[RuntimeAssuranceCheck, ...]:
        return tuple(c.check for c in self.check_results if not c.passed)


@runtime_checkable
class RuntimeAssurancePort(Protocol):
    """Runs pre-write assurance checks via Runtime Assurance / the ACP."""

    def assure(
        self, cer_payload: dict, checks: tuple[RuntimeAssuranceCheck, ...]
    ) -> AssuranceOutcome: ...


# --- ReconciliationPort ---------------------------------------------------
class ReconciliationOutcome(DomainModel):
    case_id: str
    trajectory: Trajectory
    calibration_proposal_id: Optional[str] = None


@runtime_checkable
class ReconciliationPort(Protocol):
    """Reconciles predicted vs observed outcomes via shared Reconciliation."""

    def reconcile(self, case_id: str, review_record_id: str) -> ReconciliationOutcome: ...
