"""End-to-end lifecycle driver (H5) — validation-only.

Runs a single hiring case through the full H1–H4 lifecycle using the frozen-API
services, and returns a rich ``CaseRun`` capturing every stage reached, the created
record ids, final states, and audit counts. Analysis-only attributes (group label,
protected attributes) are carried on the spec/run for fairness analysis and are
**never** passed into the operational pipeline (synthesis, generation, TAP, ActionGate,
execution) — that blindness is the leakage guarantee H5 verifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from governance_providers.api import AssertionAssessmentIntegration
from governance_providers.contracts import AssertionCoverage
from governance_providers.reference.action import DeterministicActionGovernanceProvider
from governance_providers.reference.assertion import DeterministicAssertionProvider

from ..actions.action_types import HiringActionType
from ..actions.actiongate_integration import ActionAuthorizationIntegration
from ..actions.execution_port import DeterministicHiringExecutionAdapter
from ..governance.outcomes import HiringDecisionIntent
from ..intake.intake import EvidenceProvenance, IntakeSource
from ..recommendations import ClaimAssertionEvaluator, DeterministicRecommendationGenerator
from .composition import ValidationEnv


@dataclass
class CaseSpec:
    case_id: str
    required_evidence: tuple[str, ...] = ("resume", "code_sample")
    provided_evidence: tuple[str, ...] = ("resume", "code_sample")
    assertion_coverage: AssertionCoverage = AssertionCoverage.SUPPORTED
    generator_timeout: bool = False
    generator_malformed: bool = False
    tap_timeout: bool = False
    tap_malformed: bool = False
    decision_intent: Optional[HiringDecisionIntent] = HiringDecisionIntent.ADVANCE
    action_type: Optional[HiringActionType] = HiringActionType.ADVANCE_STAGE
    action_parameters: tuple[tuple[str, str], ...] = (("stage", "onsite"),)
    action_denied: frozenset = frozenset()
    action_constrained: frozenset = frozenset()
    action_unavailable: bool = False
    exec_flags: dict = field(default_factory=dict)
    satisfy_obligations: bool = True
    reconcile: bool = True
    # analysis-only (never enters the pipeline):
    group_label: str = ""
    protected_attributes: dict = field(default_factory=dict)


@dataclass
class CaseRun:
    spec: CaseSpec
    application_id: str = ""
    candidate_subject: str = ""
    package_fingerprint: str = ""
    recommendation_id: str = ""
    recommendation_status: str = ""
    recommendation_outcome: str = ""
    decision_id: str = ""
    decision_outcome: str = ""
    override: bool = False
    action_proposal_id: str = ""
    authorized: bool = False
    authorization_outcome: str = ""
    execution_status: str = ""
    proposal_status: str = ""
    reconciliation_outcome: str = ""
    reached_stage: str = "init"
    error: str = ""


def _tap(env: ValidationEnv, spec: CaseSpec):
    provider = DeterministicAssertionProvider(
        coverage=spec.assertion_coverage, timeout=spec.tap_timeout, malformed=spec.tap_malformed)
    return ClaimAssertionEvaluator(AssertionAssessmentIntegration(provider),
                                   provider_id=provider.descriptor().provider_id)


def run_lifecycle(env: ValidationEnv, spec: CaseSpec) -> CaseRun:
    run = CaseRun(spec=spec)
    cid = spec.case_id
    req_id, jd_id = f"req-{cid}", f"jd-{cid}"
    cand_id, app_id = f"cand-{cid}", f"app-{cid}"
    ai, human = env.ai(), env.human()

    # H1 — requisition + job definition + candidate + application
    env.requisition_service.create_requisition(ai, title="Engineer", requisition_id=req_id)
    env.requisition_service.open_requisition(ai, req_id)
    env.requisition_service.draft_job_definition(
        ai, requisition_id=req_id, rubric_id="rb1", rubric_version=1,
        required_evidence_types=spec.required_evidence, job_definition_id=jd_id)
    env.requisition_service.publish_job_definition(ai, jd_id)
    env.candidate_service.register_candidate(ai, subject_id=f"subj-{cid}", candidate_id=cand_id)
    env.application_service.submit_application(
        ai, candidate_id=cand_id, requisition_id=req_id, job_definition_id=jd_id, application_id=app_id)
    env.application_service.start_screening(ai, app_id)
    for et in spec.provided_evidence:
        env.intake_service.intake_evidence(
            ai, application_id=app_id, evidence_type=et, content_hash=f"h-{cid}-{et}",
            provenance=EvidenceProvenance(source=IntakeSource.CANDIDATE_SUBMISSION, collected_by="r"),
            intake_id=f"intk-{cid}-{et}")
    run.application_id = app_id
    run.candidate_subject = f"subj-{cid}"
    run.reached_stage = "intake"

    complete = set(spec.required_evidence).issubset(set(spec.provided_evidence))
    if complete:
        env.application_service.advance_to_assessment(ai, app_id)

    # H2 — synthesis + recommendation (analysis-only attrs never passed here)
    pkg = env.synthesis_service.synthesize(ai, application_id=app_id, rubric_version=1)
    run.package_fingerprint = pkg.fingerprint
    run.reached_stage = "synthesis"
    if not complete:
        run.reached_stage = "evidence_incomplete"
        return run

    generator = DeterministicRecommendationGenerator(
        timeout=spec.generator_timeout, malformed=spec.generator_malformed)
    try:
        rec = env.generation_service.generate(
            ai, application_id=app_id, package=pkg, generator=generator, evaluator=_tap(env, spec),
            policy_refs=("pol/v1",))
    except Exception as exc:  # generator/tap failure — fail-safe, no recommendation
        run.reached_stage = "generation_failed"
        run.error = f"{type(exc).__name__}: {exc}"
        return run
    run.recommendation_id = rec.recommendation_id
    run.recommendation_status = rec.status.value
    run.recommendation_outcome = rec.outcome.value
    run.reached_stage = "recommendation"

    if spec.decision_intent is None or rec.status.value != "READY_FOR_HUMAN_REVIEW":
        return run

    # H3 — governance case + human decision
    env.governance.open_case(ai, recommendation_id=rec.recommendation_id)
    decision = env.governance.record_human_decision(
        human, recommendation_id=rec.recommendation_id, intent=spec.decision_intent)
    run.decision_id = decision.decision_id
    run.decision_outcome = decision.outcome.value
    run.override = bool(decision.override_record_id)
    run.reached_stage = "decision"

    if spec.action_type is None:
        return run

    # H4 — action proposal + authorization + execution + reconciliation
    prop = env.proposal_service.propose(
        ai, recommendation_id=rec.recommendation_id, action_type=spec.action_type,
        target_system="ats", parameters=spec.action_parameters)
    env.proposal_service.mark_ready(ai, prop.action_proposal_id)
    run.action_proposal_id = prop.action_proposal_id
    integration = ActionAuthorizationIntegration(DeterministicActionGovernanceProvider(
        denied=spec.action_denied, constrained=spec.action_constrained, unavailable=spec.action_unavailable))
    auth = env.authorization_service.authorize(ai, proposal_id=prop.action_proposal_id, integration=integration)
    run.authorized = auth.authorized
    run.authorization_outcome = auth.outcome
    run.reached_stage = "authorization"
    if not auth.authorized:
        run.proposal_status = env.proposals.get(prop.action_proposal_id).status.value
        return run

    adapter = DeterministicHiringExecutionAdapter(**spec.exec_flags)
    obligations = auth.obligations if spec.satisfy_obligations else ()
    try:
        attempt = env.execution_service.execute(
            ai, proposal_id=prop.action_proposal_id, adapter=adapter, satisfied_obligations=obligations)
        run.execution_status = attempt.execution_status
    except Exception as exc:  # obligation/expiry/malformed/target — fail-safe
        run.error = f"{type(exc).__name__}: {exc}"
    run.proposal_status = env.proposals.get(prop.action_proposal_id).status.value
    run.reached_stage = "execution"

    if spec.reconcile and run.proposal_status == "RECONCILIATION_REQUIRED":
        recon = env.reconciliation_service.reconcile(ai, proposal_id=prop.action_proposal_id)
        run.reconciliation_outcome = recon.outcome.value
        run.proposal_status = env.proposals.get(prop.action_proposal_id).status.value
        run.reached_stage = "reconciliation"
    return run
