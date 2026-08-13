"""Production RA-5 composition root (RA-5 spec §5, §12, §14).

``RiskAuthorityEvidenceRuntime`` is the explicit production facade that wires a
trusted **Evidence Admission** implementation and a trusted **Control Assurance**
evaluator into the *existing* Risk Authority application, then orchestrates:

    submit raw evidence
        → admit evidence            (EvidenceAdmissionPort)
        → assure controls           (ControlAssurancePort)
        → bind + RA re-check         (RA §8)
        → persist trusted results
        → evaluate RA                (existing RiskEngine — NOT reimplemented)
        → issue decision             (existing Decision Authority)
        → mint envelope              (existing Ed25519 EnvelopeIssuer)

It **reimplements no RA logic**: it configures ``RiskAuthorityApplication`` in
production mode and delegates. Production mode is explicit — constructing the
runtime requires both ports; an incomplete configuration fails closed in the
application constructor (RA-5 §12). Reference/conformance mode uses the
application directly and is never selected here.

The runtime mints **no** authority artifact of its own: the sole machine-execution
authority remains the RA-issued, Ed25519-signed ``RiskAuthorizationEnvelope``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Mapping, Optional

from risk_authority.api.dependencies import RiskAuthorityApplication
from risk_authority.api.schemas import (
    CreateCaseRequest,
    DecisionRequest,
    IssueEnvelopeRequest,
)
from risk_authority.crypto.keys import SigningKeyRecord
from risk_authority.domain.actions import ActionAuthorization
from risk_authority.domain.controls import ControlResult
from risk_authority.domain.decision import RiskDecision
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from risk_authority.domain.evidence import ControlEvidenceRecord
from risk_authority.domain.risk_case import RiskDecisionCase
from risk_authority.integrations.control_assurance import ControlAssurancePort
from risk_authority.integrations.ingress import TrustedEvidenceIngressPort
from risk_authority.integrations.pwc import WorkflowIRSource
from risk_authority.integrations.tap import EvidenceAdmissionPort
from risk_authority.services.decision_authority import DecisionAuthorityPort
from risk_authority.services.risk_engine import RiskEvaluation

__all__ = ["RiskAuthorityEvidenceRuntime"]


class RiskAuthorityEvidenceRuntime:
    """Explicit production composition of admission + assurance + Risk Authority."""

    def __init__(
        self,
        *,
        workflow_source: WorkflowIRSource,
        key_record: SigningKeyRecord,
        clock: Callable[[], datetime],
        evidence_admission: EvidenceAdmissionPort,
        control_assurance: ControlAssurancePort,
        evidence_ingress: TrustedEvidenceIngressPort,
        decision_authority: Optional[DecisionAuthorityPort] = None,
        issuer: str = "ugence-risk-authority",
        application: Optional[RiskAuthorityApplication] = None,
    ) -> None:
        if application is not None:
            # An explicitly supplied application MUST already be in production
            # mode with all ports wired — never silently reconfigured.
            if not getattr(application, "_production_mode", False):
                raise ValueError(
                    "supplied RiskAuthorityApplication is not in production mode "
                    "(RA-5 §12: production mode must be explicit)"
                )
            self.application = application
        else:
            # production_mode=True + admission + assurance + trusted-ingress + an
            # explicit production-authoritative decision_authority ⇒ the application
            # constructor enforces the fail-closed completeness check, the H-1/H-2
            # production guardrails (RA-5 §12, §13), and defect-(h) containment (no
            # reference decision-authority fallback in production). Envelope issuance
            # and action authorization remain Phase-5 and fail closed in production;
            # the evidence path stops at a non-executable RiskDecision.
            self.application = RiskAuthorityApplication(
                workflow_source=workflow_source,
                key_record=key_record,
                clock=clock,
                issuer=issuer,
                evidence_admission=evidence_admission,
                control_assurance=control_assurance,
                evidence_ingress=evidence_ingress,
                decision_authority=decision_authority,
                production_mode=True,
            )
        self._evidence_admission = evidence_admission
        self._control_assurance = control_assurance
        self._evidence_ingress = evidence_ingress

    # ------------------------------------------------------------------
    # Case lifecycle (delegated to the existing application — no reimpl).
    # ------------------------------------------------------------------
    def create_case(self, req: CreateCaseRequest) -> RiskDecisionCase:
        return self.application.create_case(req)

    def submit_evidence_and_evaluate(
        self,
        tenant_id: str,
        case_id: str,
        raw_evidence: tuple[ControlEvidenceRecord, ...],
        *,
        control_evidence: Optional[Mapping[str, tuple[str, ...]]] = None,
        conditions: tuple[str, ...] = (),
    ) -> RiskEvaluation:
        """Admit → assure → bind → persist trusted results → evaluate RA."""

        return self.application.evaluate_with_evidence(
            tenant_id,
            case_id,
            raw_evidence,
            control_evidence=control_evidence,
            conditions=conditions,
        )

    def issue_decision(
        self,
        tenant_id: str,
        case_id: str,
        evaluation: RiskEvaluation,
        req: DecisionRequest,
    ) -> RiskDecision:
        return self.application.issue_decision(tenant_id, case_id, evaluation, req)

    def issue_envelope(
        self, tenant_id: str, case_id: str, req: IssueEnvelopeRequest
    ) -> RiskAuthorizationEnvelope:
        return self.application.issue_envelope(tenant_id, case_id, req)

    def verify_envelope(self, tenant_id: str, envelope_id: str):
        return self.application.verify_envelope(tenant_id, envelope_id)

    def authorize_action(self, req) -> ActionAuthorization:
        return self.application.authorize_action(req)

    # ------------------------------------------------------------------
    def trusted_controls(
        self, tenant_id: str, case_id: str
    ) -> tuple[ControlResult, ...]:
        """The trusted, RA-re-checked control results persisted for a case."""

        return self.application.controls.get(tenant_id, case_id)
