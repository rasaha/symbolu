"""The end-to-end pilot workflow (Task 105).

Executes the full cross-provider workflow for one scenario through public APIs
only, with explicit early-stops, active constraint enforcement before dispatch,
obligation verification, and correlated-trace assembly. Produces a ``ScenarioRun``
of *actual* outcomes for the evaluator — it never reads the scenario's expected
region.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from decision_governance.api.contracts import (
    ActionMapping, AuthorityContext, AuthorityType, DecisionOutcome, GeneratorType,
    ParameterSchema, ProposedOutcome, VersionedRef)
from decision_governance.api.vocabulary import ReasonCode
from decision_governance.errors import ActionRequestNotExecutableError
from governance_providers.api import AssertionCoverage, AssertionGovernanceRequest, ActionGovernanceRequest

from ..composition.root import PilotComposition
from ..schemas.scenario import Scenario
from ..schemas.taxonomy import (
    ComplianceVerdict, ExecutionBehavior, ReconciliationExpectation, RecommendationPosture)
from .constraint_enforcement import EnforcementResult, enforce
from .obligations import ObligationRecord, compliance_verdict, verify_obligations
from .trace import check_completeness

_POSTURE = {
    AssertionCoverage.SUPPORTED: RecommendationPosture.ADVANCE.value,
    AssertionCoverage.CONSTRAINED: RecommendationPosture.HOLD.value,
    AssertionCoverage.UNSUPPORTED: RecommendationPosture.REJECT.value,
    AssertionCoverage.INDETERMINATE: RecommendationPosture.REQUEST_ADDITIONAL_EVIDENCE.value,
}
_DECISION = {
    AssertionCoverage.SUPPORTED: DecisionOutcome.ADVANCE,
    AssertionCoverage.CONSTRAINED: DecisionOutcome.ADVANCE,
    AssertionCoverage.UNSUPPORTED: DecisionOutcome.REJECT,
    AssertionCoverage.INDETERMINATE: DecisionOutcome.DEFER,
}
_PROCEED = {AssertionCoverage.SUPPORTED, AssertionCoverage.CONSTRAINED}


@dataclass
class ScenarioRun:
    scenario_id: str
    domain: str
    # assertion layer
    tap_outcome: str = ""
    supported_components: tuple[str, ...] = ()
    unsupported_components: tuple[str, ...] = ()
    omitted_qualifiers: tuple[str, ...] = ()
    evidence_coverage: Optional[float] = None
    tap_failsafe: bool = False
    provenance_preserved: bool = False
    # recommendation / decision
    recommendation_posture: str = ""
    recommendation_id: str = ""
    cites_assessment: bool = False
    assessment_id: str = ""
    decision_id: str = ""
    proceeded_to_action: bool = False
    # action layer
    actiongate_outcome: str = "NONE"
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    authorization_id: str = ""
    action_failsafe: bool = False
    # enforcement / execution
    enforcement_allowed: Optional[bool] = None
    enforcement_violations: tuple[str, ...] = ()
    dispatched: bool = False
    execution_behavior: str = ExecutionBehavior.NOT_DISPATCHED.value
    business_outcome: str = ""
    reconciliation: str = ReconciliationExpectation.NONE.value
    obligation_records: tuple[ObligationRecord, ...] = ()
    compliance_verdict: str = ComplianceVerdict.NOT_APPLICABLE.value
    human_review_applied: Optional[str] = None
    human_authority: str = ""
    # resolution / audit / trace
    assertion_provider_id: str = ""
    assertion_selection_rule: str = ""
    action_provider_id: str = ""
    action_selection_rule: str = ""
    audit_milestones: tuple[str, ...] = ()
    trace: dict = field(default_factory=dict)
    trace_complete: bool = False
    error: Optional[str] = None


def run_scenario(scenario: Scenario) -> ScenarioRun:
    comp = PilotComposition(scenario)
    run = ScenarioRun(scenario_id=scenario.scenario_id, domain=scenario.domain)
    trace: dict = {"scenario_id": scenario.scenario_id,
                   "evidence_ids": [e.evidence_id for e in scenario.evidence],
                   "assertion": scenario.assertion}
    try:
        _run(scenario, comp, run, trace)
    except Exception as exc:  # a pilot workflow error is recorded, never raised out
        run.error = f"{type(exc).__name__}: {exc}"
    run.trace = trace
    run.trace_complete = check_completeness(trace).complete
    return run


def _run(scenario: Scenario, comp: PilotComposition, run: ScenarioRun, trace: dict) -> None:
    # 1) resolve assertion provider (deterministic, auditable)
    tap_provider, tap_rec = comp.resolve_assertion_provider()
    run.assertion_provider_id = tap_rec.selected_id or ""
    run.assertion_selection_rule = tap_rec.selection_rule.value
    trace["assertion_provider"] = tap_rec.selected_id

    # 2-6) evaluate assertion → assessment
    evidence_refs = tuple(e.evidence_id for e in scenario.evidence)
    req = AssertionGovernanceRequest(
        assertion=scenario.assertion, assertion_type=scenario.assertion_type,
        evidence_refs=evidence_refs, source_identity=scenario.evidence[0].authority
        if scenario.evidence else "", policy_refs=(), correlation_id=scenario.scenario_id)
    result = tap_provider.evaluate(req)
    integration = comp.assertion_integration(tap_provider)
    assessment = integration.assess(req)
    run.tap_failsafe = _tap_failsafe(result)

    # human review: supply missing evidence → registry-disciplined re-evaluation
    if (result.coverage is AssertionCoverage.INDETERMINATE and scenario.human_review
            and scenario.human_review.action == "supply_evidence"
            and scenario.human_review.reevaluate_tap is not None):
        run.human_review_applied = "supply_evidence"
        run.human_authority = scenario.human_review.approver
        new_refs = evidence_refs + tuple(
            e.evidence_id for e in scenario.human_review.added_evidence)
        re_provider, _ = comp.reevaluate_assertion(
            scenario.assertion, scenario.human_review.reevaluate_tap)
        req = AssertionGovernanceRequest(
            assertion=scenario.assertion, assertion_type=scenario.assertion_type,
            evidence_refs=new_refs, correlation_id=scenario.scenario_id)
        result = re_provider.evaluate(req)
        assessment = comp.assertion_integration(re_provider).assess(req)

    run.tap_outcome = result.coverage.value
    run.supported_components = tuple(
        r.split("supported:", 1)[1] for r in result.explanation_refs
        if r.startswith("supported:"))
    run.unsupported_components = result.unsupported_elements
    run.omitted_qualifiers = result.omitted_qualifiers
    run.evidence_coverage = result.evidence_coverage
    run.provenance_preserved = bool(result.covered_evidence_refs) or \
        result.coverage in (AssertionCoverage.UNSUPPORTED, AssertionCoverage.INDETERMINATE)
    trace["tap_outcome"] = result.coverage.value

    # 7) recommendation
    posture = _POSTURE[result.coverage]
    run.recommendation_posture = posture
    assessment_id = "tap-" + assessment.fingerprint[:12]
    run.assessment_id = assessment_id
    trace["assessment_id"] = assessment_id

    dgm = comp.build_dgm(comp.control_plane(_lazy_action_provider(comp, run, trace)))
    actor, tenant = dgm.actor, dgm.tenant
    case = dgm.cases.create_case(tenant_id=tenant, decision_type="approve",
                                 subject_ids=("subject",), created_by=actor,
                                 correlation_id=scenario.scenario_id)
    trace["case_id"] = case.decision_case_id
    trace["correlation_id"] = case.correlation_id
    dgm.cases.link_assessment(case_id=case.decision_case_id, assessment_id=assessment_id,
                              version=1, actor=actor)
    rec = dgm.rec.submit_recommendation(
        case_id=case.decision_case_id, recommendation_type="assertion_support",
        proposed_outcome=ProposedOutcome[posture], generated_by=actor,
        generator_type=GeneratorType.DETERMINISTIC_POLICY,
        assessment_refs=(VersionedRef(ref_id=assessment_id, version=1, kind="assessment"),),
        reason_codes=(ReasonCode.NOT_APPLICABLE,))
    run.recommendation_id = rec.recommendation_id
    run.cites_assessment = assessment_id in {r.ref_id for r in rec.assessment_refs}
    trace["recommendation_id"] = rec.recommendation_id
    trace["recommendation_cites_assessment"] = run.cites_assessment

    # 8) decision (human authority)
    decision = dgm.dec.record_decision(
        case_id=case.decision_case_id, outcome=_DECISION[result.coverage],
        authority=AuthorityContext(authority_id=actor, authority_type=AuthorityType.HUMAN_APPROVER,
                                   decision_scope="approve"),
        decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,),
        recommendation_refs=(VersionedRef(ref_id=rec.recommendation_id, version=1,
                                          kind="recommendation"),))
    run.decision_id = decision.decision_id
    trace["decision_id"] = decision.decision_id

    proceed = result.coverage in _PROCEED
    run.proceeded_to_action = proceed
    trace["proceeded_to_action"] = proceed

    if not proceed:
        _finish_no_action(trace)
        run.audit_milestones = _milestones(dgm)
        return

    _action_and_execution(scenario, comp, run, trace, dgm, decision)
    run.audit_milestones = _milestones(dgm)


# The action provider must be resolved before building the control plane, but we
# also want its resolution recorded on the run/trace. Resolve once and cache.
def _lazy_action_provider(comp, run, trace):
    provider, rec = comp.resolve_action_provider()
    run.action_provider_id = rec.selected_id or ""
    run.action_selection_rule = rec.selection_rule.value
    trace["action_provider"] = rec.selected_id
    return provider


def _action_and_execution(scenario, comp, run, trace, dgm, decision):
    actor, tenant = dgm.actor, dgm.tenant
    pa = scenario.proposed_action
    optional = tuple(sorted(k for k in pa.parameters if k not in pa.required_fields))
    dgm.acts.publish_action_mapping(
        ActionMapping(mapping_id="m", version=1, domain_id=pa.domain_id,
                      decision_type="approve", decision_outcome=DecisionOutcome.ADVANCE,
                      permitted_action_type=pa.action_type, target_system_type=pa.target_system,
                      parameter_schema=ParameterSchema(required_fields=tuple(pa.required_fields),
                                                       optional_fields=optional)),
        actor=actor, tenant_id=tenant)
    areq = dgm.acts.create_action_request(
        decision_id=decision.decision_id, mapping_id="m", target_system=pa.target_system,
        created_by=actor, requested_parameters={k: str(v) for k, v in pa.parameters.items()})
    dgm.acts.validate_action_request(request_id=areq.action_request_id, actor=actor)
    dgm.cer.bind_cer(request_id=areq.action_request_id, actor=actor)

    resp = dgm.authz.submit_for_authorization(request_id=areq.action_request_id, actor=actor)
    run.actiongate_outcome = resp.outcome.value
    run.constraints = tuple(resp.constraints)
    run.obligations = tuple(resp.obligations)
    run.authorization_id = resp.authorization_id
    run.action_failsafe = resp.outcome.value == "INDETERMINATE"
    trace["action_provider"] = trace.get("action_provider")
    trace["authorization_outcome"] = resp.outcome.value
    trace["authorization_id"] = resp.authorization_id
    trace["constraints"] = list(resp.constraints)
    trace["obligations"] = list(resp.obligations)

    authorized = resp.outcome.value in ("AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS")
    if not authorized:
        # DENIED / INDETERMINATE → never dispatch
        run.execution_behavior = ExecutionBehavior.NOT_DISPATCHED.value
        run.reconciliation = ReconciliationExpectation.NONE.value
        run.dispatched = False
        trace.update(dispatched=False, execution_outcome="NOT_DISPATCHED",
                     reconciliation_status="NONE")
        return

    # human approval state (human authority only — never provider-fabricated)
    approval = None
    waived = False
    if scenario.human_review:
        act = scenario.human_review.action
        run.human_review_applied = run.human_review_applied or act
        run.human_authority = scenario.human_review.approver
        if act == "approve_action":
            approval = True
        elif act == "decline_action":
            approval = False

    # active constraint enforcement BEFORE dispatch
    enf: EnforcementResult = enforce(
        run.constraints, {k: str(v) for k, v in pa.parameters.items()},
        approval_granted=bool(approval))
    run.enforcement_allowed = enf.allowed
    run.enforcement_violations = enf.violations
    trace["constraint_enforcement"] = {"allowed": enf.allowed,
                                        "violations": list(enf.violations),
                                        "checked": list(enf.checked)}

    if not enf.allowed:
        run.execution_behavior = ExecutionBehavior.DISPATCH_BLOCKED_BY_CONSTRAINT.value
        run.reconciliation = ReconciliationExpectation.NONE.value
        run.dispatched = False
        run.obligation_records = verify_obligations(run.obligations, human_approval=approval,
                                                    waived=waived)
        run.compliance_verdict = compliance_verdict(run.obligation_records,
                                                    reconciliation_ok=False, dispatched=False)
        trace.update(dispatched=False, execution_outcome="BLOCKED_BY_CONSTRAINT",
                     reconciliation_status="NONE")
        return

    # dispatch through the DGM executability gate + execution service
    try:
        intent = dgm.exe.create_execution_intent(
            action_request_id=areq.action_request_id, created_by=actor)
    except ActionRequestNotExecutableError:
        run.execution_behavior = ExecutionBehavior.NOT_DISPATCHED.value
        run.dispatched = False
        trace.update(dispatched=False, execution_outcome="NOT_EXECUTABLE",
                     reconciliation_status="NONE")
        return
    trace["execution_intent_id"] = intent.execution_intent_id
    attempt = dgm.exe.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    transport = attempt.transport_status.value
    run.dispatched = True  # a dispatch attempt was made (transport failure is post-dispatch)

    if transport in ("TRANSPORT_FAILED", "TIMED_OUT"):
        run.execution_behavior = (ExecutionBehavior.TRANSPORT_FAILED.value
                                  if transport == "TRANSPORT_FAILED"
                                  else ExecutionBehavior.EXECUTION_FAILED.value)
        run.reconciliation = ReconciliationExpectation.FAILED.value
        run.business_outcome = transport
        run.obligation_records = verify_obligations(run.obligations, human_approval=approval)
        run.compliance_verdict = ComplianceVerdict.NONCOMPLIANT.value
        trace.update(dispatched=True, execution_outcome=transport,
                     reconciliation_status="FAILED")
        return

    dgm.reconcile.query_external_status(intent_id=intent.execution_intent_id, actor=actor)
    recon = dgm.reconcile.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    trace["reconciliation_id"] = recon.reconciliation_id
    run.business_outcome = recon.observed_outcome.value if recon.observed_outcome else ""
    recon_status = recon.status.value

    if run.business_outcome in ("FAILED", "REJECTED", "CANCELLED_EXTERNALLY"):
        run.execution_behavior = ExecutionBehavior.EXECUTION_FAILED.value
        run.reconciliation = ReconciliationExpectation.FAILED.value
        recon_ok = False
    elif recon_status == "RECONCILED":
        run.execution_behavior = ExecutionBehavior.DISPATCHED_SUCCESS.value
        run.reconciliation = ReconciliationExpectation.RECONCILED.value
        recon_ok = True
    else:
        run.execution_behavior = ExecutionBehavior.DISPATCHED_SUCCESS.value
        run.reconciliation = ReconciliationExpectation.MISMATCHED.value
        recon_ok = False

    run.obligation_records = verify_obligations(run.obligations, human_approval=approval,
                                               waived=waived)
    run.compliance_verdict = compliance_verdict(run.obligation_records,
                                               reconciliation_ok=recon_ok,
                                               dispatched=True)
    trace.update(dispatched=True, execution_outcome=run.business_outcome or "SUCCEEDED",
                 reconciliation_status=run.reconciliation)


def _finish_no_action(trace: dict) -> None:
    trace.setdefault("action_provider", "NONE")
    trace.update(authorization_outcome="NONE", authorization_id="",
                 constraints=[], obligations=[], dispatched=False,
                 execution_outcome="NOT_DISPATCHED", reconciliation_status="NONE")


def _tap_failsafe(result) -> bool:
    return (result.coverage is AssertionCoverage.INDETERMINATE
            and any(r.startswith("reason:provider_error") for r in result.explanation_refs))


def _milestones(dgm) -> tuple[str, ...]:
    return tuple(sorted({e.event_type.value for e in dgm.audit_events()}))
