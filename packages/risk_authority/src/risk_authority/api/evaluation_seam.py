"""``RiskEvaluationSeam`` — the production-bindable, stop-at-decision evaluation seam.

This is the smallest public composition that lets an external domain integration
(e.g. a future Cloud Scaling Phase-4 adapter) obtain a canonical Risk Authority outcome
for a neutral :class:`SubjectRiskEvaluationRequest` and **stop at the risk decision** —
never issuing an authorization envelope, never invoking ActionGate, never executing.

It composes the existing kernel primitives through the ``RiskAuthorityApplication``
facade: ``create_case → evaluate_with_evidence (production) / evaluate (reference) →
issue_decision``. It never calls ``issue_envelope`` or ``authorize_action``.

Trust boundary. The request carries only canonical subject facts + correlation context.
The trusted composition root supplies — via the factories below — the authoritative
policy resolver, the trusted evidence resolver (the RA-5 integration point), the
production Decision Authority ruler, the evaluator's authority grant, the clock and
revocation. ``RiskEvaluationSeam.production(...)`` fails closed on any missing or
reference-grade dependency; ``RiskEvaluationSeam.reference(...)`` is a visibly-labelled
conformance seam that the production factory can never yield.

RA-5 note: this seam establishes the *injection boundary* RA-5 will implement. It does
not deliver RA-5 evidence assurance. Without a real trusted-evidence provider, required
controls resolve to MISSING and the non-compensatory gate fails closed to DENY/ESCALATE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from ..domain.authority import AuthorityGrant
from ..domain.enums import AuthorityType, RiskClass, RiskOutcome, RiskRecommendation
from ..domain.errors import AuthorityDeniedError, RiskAuthorityError
from ..domain.evidence import ControlEvidenceRecord
from ..integrations.evaluation_contracts import (
    ReferenceControlEvidenceResolver,
    ReferencePolicyResolver,
    SubjectRiskDecision,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequest,
    SubjectRiskNonDecisionReason,
    SUPPORTED_REQUEST_SCHEMA_VERSIONS,
    PolicyResolverPort,
    TrustedControlEvidenceResolverPort,
    disposition_for_outcome,
)
from ..integrations.control_assurance import ControlAssurancePort
from ..integrations.ingress import TrustedEvidenceIngressPort
from ..integrations.pwc import WorkflowIRSource
from ..integrations.tap import EvidenceAdmissionPort
from ..services.decision_authority import DecisionAuthorityPort, ReferenceDecisionAuthority
from ..services.revocation import RevocationState
from ..crypto.hashing import digest as _digest
from .dependencies import RiskAuthorityApplication
from .schemas import CreateCaseRequest, DecisionRequest, EvaluateRequest

__all__ = ["RiskEvaluationSeam", "SeamConfigurationError"]


class SeamConfigurationError(RiskAuthorityError):
    """Raised when the seam is constructed with an unsafe/incomplete configuration."""


_RECOMMENDATION_TO_OUTCOME = {
    RiskRecommendation.ALLOW: RiskOutcome.ALLOW,
    RiskRecommendation.ALLOW_WITH_CONDITIONS: RiskOutcome.ALLOW_WITH_CONDITIONS,
    RiskRecommendation.ESCALATE: RiskOutcome.ESCALATE,
    RiskRecommendation.DENY: RiskOutcome.DENY,
}


@dataclass(frozen=True)
class _Outcome:
    disposition: SubjectRiskDisposition
    reason: Optional[SubjectRiskNonDecisionReason] = None


class RiskEvaluationSeam:
    """Compose the kernel into a stop-at-decision subject-risk evaluation.

    Construct via :meth:`production` or :meth:`reference`; the initializer is internal.
    """

    def __init__(
        self,
        *,
        app: RiskAuthorityApplication,
        policy_resolver: PolicyResolverPort,
        evidence_resolver: TrustedControlEvidenceResolverPort,
        evaluator_principal_id: str,
        clock: Callable[[], datetime],
        production: bool,
        reference_grant_factory: Optional[Callable[[SubjectRiskEvaluationRequest, RiskClass], AuthorityGrant]] = None,
    ) -> None:
        self._app = app
        self._policy_resolver = policy_resolver
        self._evidence_resolver = evidence_resolver
        self._evaluator_principal_id = evaluator_principal_id
        self._clock = clock
        self._production = production
        self._reference_grant_factory = reference_grant_factory

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(
        cls,
        *,
        workflow_source: WorkflowIRSource,
        policy_resolver: PolicyResolverPort,
        evidence_resolver: TrustedControlEvidenceResolverPort,
        evidence_admission: EvidenceAdmissionPort,
        control_assurance: ControlAssurancePort,
        evidence_ingress: TrustedEvidenceIngressPort,
        decision_authority: DecisionAuthorityPort,
        evaluator_grant: AuthorityGrant,
        key_record,
        clock: Callable[[], datetime],
        revocation: Optional[RevocationState] = None,
    ) -> "RiskEvaluationSeam":
        """Build a production seam. Fails closed on any reference-grade dependency.

        ``key_record`` is required by the underlying facade for its (unused here)
        envelope path; the seam never issues an envelope, so no signing occurs on the
        stop-at-decision path.
        """
        if getattr(policy_resolver, "is_production_authoritative", False) is not True:
            raise SeamConfigurationError(
                "production seam requires a production-authoritative PolicyResolverPort "
                "(is_production_authoritative=True); a reference resolver is refused."
            )
        if getattr(evidence_resolver, "is_production_authoritative", False) is not True:
            raise SeamConfigurationError(
                "production seam requires a production-authoritative "
                "TrustedControlEvidenceResolverPort; a reference resolver is refused."
            )
        if isinstance(decision_authority, ReferenceDecisionAuthority) or (
            getattr(decision_authority, "is_production_authoritative", False) is not True
        ):
            raise SeamConfigurationError(
                "production seam requires a production-authoritative DecisionAuthorityPort "
                "over ugence-decision-authority; the reference ruler is refused (defect h)."
            )
        if evaluator_grant is None or not isinstance(evaluator_grant, AuthorityGrant):
            raise SeamConfigurationError("production seam requires an injected AuthorityGrant")
        # The facade itself re-validates evidence/ingress/assurance and the injected
        # ruler in production mode (fail closed on incomplete config).
        app = RiskAuthorityApplication(
            workflow_source=workflow_source,
            key_record=key_record,
            clock=clock,
            evidence_admission=evidence_admission,
            control_assurance=control_assurance,
            evidence_ingress=evidence_ingress,
            decision_authority=decision_authority,
            revocation=revocation,
            production_mode=True,
        )
        app.authority.add_grant(evaluator_grant)
        return cls(
            app=app,
            policy_resolver=policy_resolver,
            evidence_resolver=evidence_resolver,
            evaluator_principal_id=evaluator_grant.principal_id,
            clock=clock,
            production=True,
        )

    @classmethod
    def reference(
        cls,
        *,
        workflow_source: WorkflowIRSource,
        key_record,
        clock: Callable[[], datetime],
        policy_resolver: Optional[PolicyResolverPort] = None,
        evidence_resolver: Optional[TrustedControlEvidenceResolverPort] = None,
        evaluator_principal_id: str = "ra-reference-evaluator",
    ) -> "RiskEvaluationSeam":
        """Build a REFERENCE/conformance seam (visibly labelled; never production).

        Uses the in-package reference ruler and, for a passing conformance case,
        mints a request-scoped reference grant. It never trusts caller-supplied
        controls (the request has none) and cannot be produced by :meth:`production`.
        """
        app = RiskAuthorityApplication(
            workflow_source=workflow_source,
            key_record=key_record,
            clock=clock,
            production_mode=False,
        )

        def _grant(req: SubjectRiskEvaluationRequest, risk_class: RiskClass) -> AuthorityGrant:
            return AuthorityGrant(
                principal_id=evaluator_principal_id,
                tenant_id=req.tenant_id,
                authority_type=AuthorityType.RISK_APPROVAL,
                domains=(req.requested_domain,),
                allowed_risk_classes=(risk_class,),
                max_autonomy=max(req.requested_autonomy_level, 0),
                delegated_by="ra-reference-root",
                grantable_scope=req.requested_scope.normalized(),
            )

        return cls(
            app=app,
            policy_resolver=policy_resolver or ReferencePolicyResolver(by_purpose_domain={}),
            evidence_resolver=evidence_resolver or ReferenceControlEvidenceResolver(),
            evaluator_principal_id=evaluator_principal_id,
            clock=clock,
            production=False,
            reference_grant_factory=_grant,
        )

    # ------------------------------------------------------------------ evaluate
    def evaluate(self, request: SubjectRiskEvaluationRequest) -> SubjectRiskDecision:
        """Evaluate ``request`` and return a stop-at-decision result (fail closed)."""
        if not isinstance(request, SubjectRiskEvaluationRequest):
            raise SeamConfigurationError("request must be a SubjectRiskEvaluationRequest")
        now = request.evaluation_time or self._clock()
        req_digest = request.digest()

        def _not_evaluated(reason: SubjectRiskNonDecisionReason, *codes: str) -> SubjectRiskDecision:
            return SubjectRiskDecision(
                request_digest=req_digest,
                subject_digest=request.subject_digest,
                tenant_id=request.tenant_id,
                disposition=SubjectRiskDisposition.NOT_EVALUATED,
                evaluator_principal_id=self._evaluator_principal_id,
                evaluated_at=now,
                non_decision_reason=reason,
                reason_codes=tuple(codes),
                correlation_id=request.correlation_id,
                idempotency_key=request.idempotency_key,
            )

        if request.schema_version not in SUPPORTED_REQUEST_SCHEMA_VERSIONS:
            return _not_evaluated(SubjectRiskNonDecisionReason.UNSUPPORTED_SCHEMA_VERSION,
                                  f"schema:{request.schema_version}")

        risk_class = request.requested_risk_class or RiskClass.HIGH

        # --- 1. Trusted policy resolution (caller never selects policy). ----------
        try:
            workflow = self._policy_resolver.resolve(
                tenant_id=request.tenant_id,
                purpose=request.requested_purpose,
                domain=request.requested_domain,
                risk_class=request.requested_risk_class,
                requested_scope=request.requested_scope,
                now=now,
            )
        except Exception as exc:  # noqa: BLE001 - ambiguity / resolver failure ⇒ fail closed
            return _not_evaluated(SubjectRiskNonDecisionReason.AMBIGUOUS_POLICY,
                                  f"resolver_error:{type(exc).__name__}")
        if workflow is None:
            return _not_evaluated(SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY)

        # --- 2. Create the case (subject facts + resolved policy). ----------------
        try:
            case = self._app.create_case(CreateCaseRequest(
                tenant_id=request.tenant_id,
                case_id=None,
                subject_id=request.subject_id,
                model_id=request.subject_id,
                purpose=request.requested_purpose,
                domain=request.requested_domain,
                jurisdictions=request.jurisdictions,
                tools=request.requested_tools,
                autonomy_level=request.requested_autonomy_level,
                data_classes=request.requested_data_classes,
                workflow_ir_id=workflow.workflow_ir_id,
                workflow_ir_version=workflow.version,
                inherent_risk=risk_class,
                residual_risk=risk_class,
                correlation_id=request.correlation_id or "",
            ))
        except RiskAuthorityError as exc:
            return _not_evaluated(SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY,
                                  f"create_case:{type(exc).__name__}")

        # --- 3. Evaluate (trusted evidence in production; empty controls in reference).
        try:
            if self._production:
                raw = self._resolve_evidence(request, case, workflow.digest, now)
                evaluation = self._app.evaluate_with_evidence(
                    request.tenant_id, case.case_id, raw)
            else:
                evaluation = self._app.evaluate(
                    request.tenant_id, case.case_id, EvaluateRequest(control_results=()))
        except Exception as exc:  # noqa: BLE001 - evaluator failure ⇒ typed non-decision
            return _not_evaluated(SubjectRiskNonDecisionReason.EVALUATOR_UNAVAILABLE,
                                  f"evaluate:{type(exc).__name__}")

        eval_snapshot = _canonical(evaluation)
        outcome = _RECOMMENDATION_TO_OUTCOME[evaluation.recommendation]

        # --- 4. Bind a decision where the kernel permits it; stop there. ----------
        # In reference mode the reference ruler mints a decision for any outcome; in
        # production the facade only reaches issue_decision from AUTHORITY_REVIEW
        # (i.e. an ALLOW-family case). A denied production case has no binding
        # decision — its canonical evaluation stands.
        if not self._production and self._reference_grant_factory is not None:
            self._app.authority.add_grant(self._reference_grant_factory(request, risk_class))

        decision = None
        try:
            decision = self._app.issue_decision(
                request.tenant_id,
                case.case_id,
                evaluation,
                DecisionRequest(
                    principal_id=self._evaluator_principal_id,
                    requested_scope=request.requested_scope,
                    evidence_snapshot_digest=_digest(sorted(request.evidence_references)),
                    model_digest=request.subject_digest,
                ),
            )
        except AuthorityDeniedError as exc:
            # The risk evaluation passed but the configured evaluator principal is not
            # entitled to bind it — a composition/authority configuration gap.
            return _not_evaluated(SubjectRiskNonDecisionReason.AUTHORITY_UNAVAILABLE,
                                  f"authority_denied:{len(exc.args)}")
        except RiskAuthorityError:
            # Not in AUTHORITY_REVIEW (production denial) or no grant: the evaluation
            # is the artifact. If it was an ALLOW-family evaluation we could not bind,
            # that is an authority-configuration gap, not a pass (see below).
            decision = None

        if decision is not None:
            outcome = decision.outcome

        # An ALLOW-family evaluation that produced no binding decision must never be
        # reported as a risk PASS: without a bound decision there is no authority-
        # granting artifact, so it is a typed non-decision (fail closed).
        allow_family = outcome in (RiskOutcome.ALLOW, RiskOutcome.ALLOW_WITH_CONDITIONS)
        if allow_family and decision is None:
            return _not_evaluated(SubjectRiskNonDecisionReason.AUTHORITY_UNAVAILABLE,
                                  "allow_without_binding_decision")

        disposition = disposition_for_outcome(outcome)
        decision_snapshot = _canonical(decision) if decision is not None else None
        reason_codes = tuple(evaluation.applicable_rules)
        expires_at = decision.expires_at if decision is not None else None

        return SubjectRiskDecision(
            request_digest=req_digest,
            subject_digest=request.subject_digest,
            tenant_id=request.tenant_id,
            disposition=disposition,
            evaluator_principal_id=self._evaluator_principal_id,
            evaluated_at=now,
            risk_outcome=outcome,
            evaluation_snapshot=eval_snapshot,
            decision_snapshot=decision_snapshot,
            workflow_ir_digest=workflow.digest,
            expires_at=expires_at,
            reason_codes=reason_codes,
            correlation_id=request.correlation_id,
            idempotency_key=request.idempotency_key,
        )

    # ------------------------------------------------------------------ helpers
    def _resolve_evidence(
        self,
        request: SubjectRiskEvaluationRequest,
        case,
        workflow_digest: str,
        now: datetime,
    ) -> tuple[ControlEvidenceRecord, ...]:
        records = self._evidence_resolver.resolve(
            tenant_id=request.tenant_id,
            risk_case_id=case.case_id,
            workflow_ir_digest=workflow_digest,
            policy_digest=workflow_digest,
            subject_id=request.subject_id,
            evidence_references=request.evidence_references,
            now=now,
        )
        # Only genuine ControlEvidenceRecords are forwarded; anything else is dropped
        # so a control loses that backing and fails closed (MISSING).
        return tuple(r for r in records if isinstance(r, ControlEvidenceRecord))


def _canonical(value) -> dict:
    from ..crypto.canonical import to_canonical_obj

    return to_canonical_obj(value)
