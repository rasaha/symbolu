"""Shared DGM flow helpers (benchmark-owned, kernel API only).

Provides the case→assessment→recommendation→decision record flow and the
action→authorize→enforce→execute→reconcile flow. Strategies inject their own
provider-derived inputs (TAP coverage / ActionGate control plane); this module
imports no provider, so it is safe for every strategy's import graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from decision_governance.api.contracts import (
    ActionMapping, AuthorityContext, AuthorityType, DecisionOutcome, GeneratorType,
    ParameterSchema, ProposedOutcome, VersionedRef)
from decision_governance.api.vocabulary import ReasonCode
from decision_governance.errors import ActionRequestNotExecutableError

from .dgm import DGMServices
from .enforcement import enforce
from .obligations import compliance_verdict, verify_obligations

POSTURE = {"SUPPORTED": "ADVANCE", "CONSTRAINED": "HOLD",
           "UNSUPPORTED": "REJECT", "INDETERMINATE": "REQUEST_ADDITIONAL_EVIDENCE"}
_DECISION = {"SUPPORTED": DecisionOutcome.ADVANCE, "CONSTRAINED": DecisionOutcome.ADVANCE,
             "UNSUPPORTED": DecisionOutcome.REJECT, "INDETERMINATE": DecisionOutcome.DEFER}
PROCEED = {"SUPPORTED", "CONSTRAINED"}


def technical_valid(scenario) -> bool:
    """Ordinary application validation: required action fields are present."""
    params = scenario.proposed_action.parameters
    return all(f in params for f in scenario.proposed_action.required_fields)


@dataclass
class CaseFlow:
    case_id: str
    correlation_id: str
    assessment_id: str
    recommendation_id: str
    cites_assessment: bool
    decision_id: str
    proceeded: bool


def run_case_flow(dgm: DGMServices, scenario, *, coverage: str, assessment_id: str) -> CaseFlow:
    actor, tenant = dgm.actor, dgm.tenant
    posture = POSTURE[coverage]
    case = dgm.cases.create_case(tenant_id=tenant, decision_type="approve",
                                 subject_ids=("subject",), created_by=actor,
                                 correlation_id=scenario.scenario_id)
    dgm.cases.link_assessment(case_id=case.decision_case_id, assessment_id=assessment_id,
                              version=1, actor=actor)
    rec = dgm.rec.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="assertion_support",
        proposed_outcome=ProposedOutcome[posture], generated_by=actor,
        generator_type=GeneratorType.DETERMINISTIC_POLICY,
        assessment_refs=(VersionedRef(ref_id=assessment_id, version=1, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    decision = dgm.dec.record_decision(
        case_id=case.decision_case_id, outcome=_DECISION[coverage],
        authority=AuthorityContext(authority_id=actor, authority_type=AuthorityType.HUMAN_APPROVER,
                                   decision_scope="approve"),
        decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,),
        recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1,
                                          kind="recommendation"),))
    return CaseFlow(
        case_id=case.decision_case_id, correlation_id=case.correlation_id,
        assessment_id=assessment_id, recommendation_id=rec.recommendation_id,
        cites_assessment=assessment_id in {r.ref_id for r in rec.assessment_refs},
        decision_id=decision.decision_id, proceeded=coverage in PROCEED)


@dataclass
class ActionFlow:
    authorization_outcome: str = "NOT_PERFORMED"
    authorization_id: str = ""
    constraints: tuple = ()
    obligations: tuple = ()
    enforcement_allowed: Optional[bool] = None
    enforcement_violations: tuple = ()
    dispatched: bool = False
    execution_outcome: str = "NOT_PERFORMED"
    reconciliation: str = "NOT_PERFORMED"
    obligation_records: tuple = ()
    compliance: str = "NOT_APPLICABLE"
    action_failsafe: bool = False


def run_action_flow(dgm: DGMServices, scenario, decision_id: str, *,
                    approval: Optional[bool], waived: bool = False) -> ActionFlow:
    """Authorize → enforce constraints → dispatch → reconcile through DGM + a control plane."""
    actor, tenant = dgm.actor, dgm.tenant
    pa = scenario.proposed_action
    out = ActionFlow()

    optional = tuple(sorted(k for k in pa.parameters if k not in pa.required_fields))
    dgm.acts.publish_action_mapping(
        ActionMapping(mapping_id="m", version=1, domain_id=pa.domain_id,
                      decision_type="approve", decision_outcome=DecisionOutcome.ADVANCE,
                      permitted_action_type=pa.action_type, target_system_type=pa.target_system,
                      parameter_schema=ParameterSchema(required_fields=tuple(pa.required_fields),
                                                       optional_fields=optional)),
        actor=actor, tenant_id=tenant)
    areq = dgm.acts.create_action_request(
        decision_id=decision_id, mapping_id="m", target_system=pa.target_system,
        created_by=actor, requested_parameters={k: str(v) for k, v in pa.parameters.items()})
    dgm.acts.validate_action_request(request_id=areq.action_request_id, actor=actor)
    dgm.cer.bind_cer(request_id=areq.action_request_id, actor=actor)

    resp = dgm.authz.submit_for_authorization(request_id=areq.action_request_id, actor=actor)
    out.authorization_outcome = resp.outcome.value
    out.authorization_id = resp.authorization_id
    out.constraints = tuple(resp.constraints)
    out.obligations = tuple(resp.obligations)
    out.action_failsafe = resp.outcome.value == "INDETERMINATE"

    if resp.outcome.value not in ("AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"):
        out.execution_outcome = "NOT_DISPATCHED"
        out.reconciliation = "NONE"
        return out

    enf = enforce(out.constraints, {k: str(v) for k, v in pa.parameters.items()},
                  approval_granted=bool(approval))
    out.enforcement_allowed = enf.allowed
    out.enforcement_violations = enf.violations
    if not enf.allowed:
        out.execution_outcome = "BLOCKED_BY_CONSTRAINT"
        out.reconciliation = "NONE"
        out.obligation_records = verify_obligations(out.obligations, human_approval=approval,
                                                    waived=waived)
        out.compliance = compliance_verdict(out.obligation_records, reconciliation_ok=False,
                                            dispatched=False)
        return out

    try:
        intent = dgm.exe.create_execution_intent(action_request_id=areq.action_request_id,
                                                 created_by=actor)
    except ActionRequestNotExecutableError:
        out.execution_outcome = "NOT_EXECUTABLE"
        out.reconciliation = "NONE"
        return out
    attempt = dgm.exe.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    out.dispatched = True
    transport = attempt.transport_status.value
    if transport in ("TRANSPORT_FAILED", "TIMED_OUT"):
        out.execution_outcome = transport
        out.reconciliation = "FAILED"
        out.obligation_records = verify_obligations(out.obligations, human_approval=approval,
                                                    waived=waived)
        out.compliance = "NONCOMPLIANT"
        return out

    dgm.reconcile.query_external_status(intent_id=intent.execution_intent_id, actor=actor)
    recon = dgm.reconcile.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    out.execution_outcome = recon.observed_outcome.value if recon.observed_outcome else "SUCCEEDED"
    recon_status = recon.status.value
    if out.execution_outcome in ("FAILED", "REJECTED", "CANCELLED_EXTERNALLY"):
        out.reconciliation, recon_ok = "FAILED", False
    elif recon_status == "RECONCILED":
        out.reconciliation, recon_ok = "RECONCILED", True
    else:
        out.reconciliation, recon_ok = "MISMATCHED", False
    out.obligation_records = verify_obligations(out.obligations, human_approval=approval,
                                                waived=waived)
    out.compliance = compliance_verdict(out.obligation_records, reconciliation_ok=recon_ok,
                                        dispatched=True)
    return out
