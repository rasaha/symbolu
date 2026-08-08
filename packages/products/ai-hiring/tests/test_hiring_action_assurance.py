"""Tests for the action-assurance orchestration spine (spec §21 step 5).

decision → ActionGate authorization → Runtime Assurance → HRIS execution handoff
→ Execution Receipt → Reconciliation. Covers sequencing, fail-closed behavior,
payload binding, port-call ordering, standalone operation, receipt integrity, and
reconciliation classification.
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone

import pytest

from ugence_ai_hiring.hiring_policy import (
    ActionConstraints,
    DimensionEmphasis,
    HiringPolicy,
    HiringPolicyCompiler,
    MandatoryGateType,
    Requirements,
    RoleRef,
    project_contract,
)
from ugence_ai_hiring.hiring_policy.enums import HiringEvidenceClass
import ugence_ai_hiring.hiring_decision as hd
from ugence_ai_hiring.hiring_decision import (
    ActionAuthorizationDenied,
    ExecutionStatus,
    FailClosedError,
    HiringDecisionService,
    PayloadMutationError,
    ReconciliationStatus,
    RuntimeAssuranceNotClear,
)
from ugence_ai_hiring.hiring_decision.enums import (
    ActionAuthorizationVerdict,
    AssuranceResult,
    DecisionDisposition,
    EligibilityStatus,
    RecommendationDisposition,
)
from ugence_ai_hiring.hiring_decision.ports import (
    ActionAuthorizationOutcome,
    AssuranceCheckResult,
    AssuranceOutcome,
    ExecutionOutcome,
    HRISExecutionPort,
)
from ugence_ai_hiring.hiring_decision.service import AuthorizedAction, ClearedAction

from .hiring_decision_fakes import FakeHRISExecutionPort, FakeReconciliationPort

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PROV = hd.AssessmentProvenance(engine="compat-engine-v1")


# --- recording port fakes -------------------------------------------------
class RecAuth:
    def __init__(self, log, *, ok=True, echo_digest=True, wrong_digest=False):
        self.log, self.ok, self.echo, self.wrong = log, ok, echo_digest, wrong_digest
        self.calls = []

    def authorize(self, payload):
        self.log.append("AUTH")
        self.calls.append(payload)
        verdict = ActionAuthorizationVerdict.AUTHORIZED if self.ok else ActionAuthorizationVerdict.DENIED
        digest = ""
        if self.echo:
            digest = "WRONG" * 12 if self.wrong else payload["action_digest"]
        return ActionAuthorizationOutcome(verdict=verdict, authorization_id="auth-1",
                                          authorized_action_digest=digest, reason="fake")


class RecRuntime:
    def __init__(self, log, *, clear=True):
        self.log, self.clear = log, clear
        self.calls = []

    def assure(self, payload, checks):
        self.log.append("ASSURE")
        self.calls.append((payload, checks))
        res = AssuranceResult.ASSURED if self.clear else AssuranceResult.BLOCKED
        crs = tuple(AssuranceCheckResult(check=c, passed=self.clear) for c in checks)
        return AssuranceOutcome(result=res, check_results=crs, assurance_id="assure-1")


class RecExec:
    def __init__(self, log, *, status=ExecutionStatus.SUCCEEDED, mirror=True, hris_state=None):
        self.log, self.status, self.mirror = log, status, mirror
        self.hris_state = {"worker_id": "W123"} if hris_state is None else hris_state
        self.calls = []

    def execute(self, payload):
        self.log.append("EXEC")
        self.calls.append(payload)
        a = payload["action"]
        executed = None
        if self.mirror and self.status is ExecutionStatus.SUCCEEDED:
            executed = hd.HiringActionSnapshot(level=a["level"], salary=a["salary_ceiling"],
                salary_currency=a["currency"], role_id=payload["subject"]["role_id"],
                location=a["location"], employment_type=a["employment_type"])
        return ExecutionOutcome(execution_reference="hris-exec-1", status=self.status,
            result_digest="rd-1", executed_action=executed, hris_state=dict(self.hris_state))


# --- fixtures -------------------------------------------------------------
def build_contract():
    policy = HiringPolicy(
        policy_id="pol-arch",
        role=RoleRef(job_definition_id="jd-arch", title="Senior Architect", seniority_level="L5"),
        requirements=Requirements(required_skills=("AWS",), mandatory=(MandatoryGateType.REQUIRED_SKILLS,),
                                  emphasis=(("TECHNICAL", DimensionEmphasis.PRIMARY),)),
        action_constraints=ActionConstraints(salary_ceiling=220000, approved_level="L5",
                                            approved_roles=("Senior Architect",), allowed_locations=("NYC",)),
        approval_chain=("Hiring Manager", "Director", "VP Eng"), authored_by="hr",
    )
    ir = HiringPolicyCompiler().compile(policy)
    return project_contract(ir, job_definition_id="jd-arch")


def decided_case(hdc):
    cref = hd.contract_ref_of(hdc)
    assess = (hd.DimensionAssessment(dimension="TECHNICAL", outcome=hd.AssessmentOutcome.SCORED,
                                     score=90, confidence=0.9, evidence_refs=("ln-1",), provenance=PROV),)
    evidence = (hd.AdmittedEvidence(evidence_id="e1", evidence_class=HiringEvidenceClass.CODING_ASSESSMENT,
                                    admitted=True, lineage_node_id="ln-1", attributes={"required_skills_met": True}),)
    gr = hd.MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    elig = hd.derive_eligibility(gr, cref)
    pa = hd.ProposedAction(level="L5", salary=200000, role="Senior Architect", location="NYC",
                           employment_type=hd.EmploymentType.FULL_TIME)
    rec = hd.build_recommendation(candidate_id="c1", role_id="jd-arch", contract_ref=cref,
                                  admitted_evidence=evidence, dimension_assessments=assess, gate_results=gr,
                                  eligibility=elig, proposed_action=pa, action_constraints=hdc.action_constraints)
    case = (hd.HiringDecisionCase(candidate_id="c1", role_id="jd-arch", contract_ref=cref)
            .record_evidence(evidence).record_assessments(assess).record_gate_results(gr, elig)
            .record_recommendation(rec))
    outcome = hd.DecisionAuthorityOutcome(recommendation_id=rec.recommendation_id,
                                          disposition=DecisionDisposition.ADVANCE, binding=True,
                                          authority_id="hm-alex", rationale_job_related="strong")
    return case.record_decision(outcome)


def make_service(log, *, auth=None, rt=None, ex=None, recon=None):
    return HiringDecisionService(
        action_authorization_port=auth or RecAuth(log),
        runtime_assurance_port=rt or RecRuntime(log),
        execution_port=ex or RecExec(log),
        reconciliation_port=recon,
    )


# --- sequencing + ordering ------------------------------------------------
def test_happy_path_full_spine_reconciled():
    hdc = build_contract()
    case = decided_case(hdc)
    log = []
    svc = make_service(log)
    result = svc.run(case, hdc, actor="hm-alex", now=NOW)
    assert result.receipt.execution_status is ExecutionStatus.SUCCEEDED
    assert result.reconciliation.status is ReconciliationStatus.RECONCILED


def test_port_call_ordering_is_auth_then_assure_then_exec():
    hdc = build_contract()
    case = decided_case(hdc)
    log = []
    make_service(log).run(case, hdc, actor="hm-alex", now=NOW)
    assert log == ["AUTH", "ASSURE", "EXEC"]


def test_runtime_receives_contract_assurance_checks():
    hdc = build_contract()
    case = decided_case(hdc)
    log = []
    rt = RecRuntime(log)
    make_service(log, rt=rt).run(case, hdc, actor="hm-alex", now=NOW)
    _payload, checks = rt.calls[0]
    assert checks == hdc.runtime_assurance_checks


# --- fail-closed behavior -------------------------------------------------
def test_no_binding_decision_no_action_request():
    hdc = build_contract()
    case = decided_case(hdc)
    no_decision = case.model_copy(update={"decision": None})
    log = []
    auth = RecAuth(log)
    svc = make_service(log, auth=auth)
    with pytest.raises(FailClosedError):
        svc.build_action_request(no_decision, hdc)
    assert auth.calls == []


def test_not_eligible_no_action():
    hdc = build_contract()
    case = decided_case(hdc)
    not_elig = case.eligibility.model_copy(update={"status": EligibilityStatus.NOT_ELIGIBLE})
    case2 = case.model_copy(update={"eligibility": not_elig})
    with pytest.raises(FailClosedError):
        make_service([]).build_action_request(case2, hdc)


def test_eligibility_pending_no_action():
    hdc = build_contract()
    case = decided_case(hdc)
    pending = case.eligibility.model_copy(update={"status": EligibilityStatus.ELIGIBILITY_PENDING})
    case2 = case.model_copy(update={"eligibility": pending})
    with pytest.raises(FailClosedError):
        make_service([]).build_action_request(case2, hdc)


def test_binding_decision_not_advance_no_action():
    hdc = build_contract()
    case = decided_case(hdc)
    decl = case.decision.model_copy(update={"disposition": DecisionDisposition.DECLINE})
    case2 = case.model_copy(update={"decision": decl})
    with pytest.raises(FailClosedError):
        make_service([]).build_action_request(case2, hdc)


def test_contract_binding_mismatch_rejected():
    hdc = build_contract()
    case = decided_case(hdc)
    other = hdc.model_copy(update={"version": 99})
    with pytest.raises(hd.ContractBindingError):
        make_service([]).build_action_request(case, other)


def test_actiongate_denial_blocks_runtime_and_execution():
    hdc = build_contract()
    case = decided_case(hdc)
    log = []
    rt, ex = RecRuntime(log), RecExec(log)
    svc = make_service(log, auth=RecAuth(log, ok=False), rt=rt, ex=ex)
    with pytest.raises(ActionAuthorizationDenied):
        svc.run(case, hdc, actor="hm-alex", now=NOW)
    assert rt.calls == [] and ex.calls == []
    assert log == ["AUTH"]


def test_runtime_not_clear_blocks_execution():
    hdc = build_contract()
    case = decided_case(hdc)
    log = []
    ex = RecExec(log)
    svc = make_service(log, rt=RecRuntime(log, clear=False), ex=ex)
    with pytest.raises(RuntimeAssuranceNotClear):
        svc.run(case, hdc, actor="hm-alex", now=NOW)
    assert ex.calls == []
    assert log == ["AUTH", "ASSURE"]


# --- payload binding ------------------------------------------------------
def test_actiongate_authorizing_different_digest_is_rejected():
    hdc = build_contract()
    case = decided_case(hdc)
    svc = make_service([], auth=RecAuth([], wrong_digest=True))
    ar = svc.build_action_request(case, hdc)
    with pytest.raises(PayloadMutationError):
        svc.authorize(ar, now=NOW)


def test_action_payload_mutation_after_authorization_rejected():
    hdc = build_contract()
    case = decided_case(hdc)
    log = []
    ex = RecExec(log)
    svc = make_service(log, ex=ex)
    ar = svc.build_action_request(case, hdc)
    authorized = svc.authorize(ar, now=NOW)
    cleared = svc.assure(authorized, hdc.runtime_assurance_checks, now=NOW)
    # tamper: swap in a different action but keep the old authorized digest
    tampered_ar = ar.model_copy(update={"location": "REMOTE-EU"})
    tampered_authorized = AuthorizedAction(tampered_ar, authorized.outcome, authorized.authorized_digest, NOW)
    tampered_cleared = ClearedAction(tampered_authorized, cleared.assurance, NOW)
    with pytest.raises(PayloadMutationError):
        svc.execute(case, tampered_cleared, actor="hm-alex", now=NOW)
    assert ex.calls == []


def test_action_request_digest_is_semantic_not_identity():
    hdc = build_contract()
    case = decided_case(hdc)
    ar = make_service([]).build_action_request(case, hdc)
    same_action_new_id = ar.model_copy(update={"action_request_id": "hact-different"})
    assert same_action_new_id.content_digest == ar.content_digest
    different_action = ar.model_copy(update={"level": "L6"})
    assert different_action.content_digest != ar.content_digest


# --- execution receipt integrity -----------------------------------------
def test_receipt_binds_every_reference():
    hdc = build_contract()
    case = decided_case(hdc)
    result = make_service([]).run(case, hdc, actor="hm-alex", now=NOW)
    r = result.receipt
    assert r.decision_case_id == case.case_id
    assert r.contract_ref.ir_digest == case.contract_ref.ir_digest
    assert r.contract_ref.version == case.contract_ref.version
    assert r.binding_decision_id == case.decision.decision_id
    assert r.binding_authority_id == "hm-alex"
    assert r.action_request_id == result.action_request.action_request_id
    assert r.action_request_digest == result.action_request.content_digest
    assert r.authorization_ref == "auth-1"
    assert r.assurance_ref == "assure-1"
    assert r.hris_execution_ref == "hris-exec-1"
    assert r.actor == "hm-alex"
    assert r.authorized_at == NOW and r.assured_at == NOW and r.executed_at == NOW
    assert r.execution_status is ExecutionStatus.SUCCEEDED
    assert r.result_digest == "rd-1"


# --- reconciliation classification ---------------------------------------
def test_reconciliation_deviation_when_executed_differs():
    hdc = build_contract()
    case = decided_case(hdc)
    svc = make_service([])
    ar = svc.build_action_request(case, hdc)
    authorized = svc.authorize(ar, now=NOW)
    cleared = svc.assure(authorized, hdc.runtime_assurance_checks, now=NOW)
    # HRIS executed a different location than authorized
    class DevExec:
        def execute(self, payload):
            a = payload["action"]
            snap = hd.HiringActionSnapshot(level=a["level"], salary=a["salary_ceiling"],
                salary_currency=a["currency"], role_id=payload["subject"]["role_id"],
                location="REMOTE-EU", employment_type=a["employment_type"])
            return ExecutionOutcome(execution_reference="h", status=ExecutionStatus.SUCCEEDED,
                                    executed_action=snap, hris_state={"worker_id": "W1"})
    svc2 = HiringDecisionService(action_authorization_port=RecAuth([]),
        runtime_assurance_port=RecRuntime([]), execution_port=DevExec())
    result = svc2.execute(case, cleared, actor="hm-alex", now=NOW)
    record = svc2.reconcile(case, result, now=NOW)
    assert record.status is ReconciliationStatus.DEVIATION


def test_reconciliation_partial_when_hris_state_missing():
    hdc = build_contract()
    case = decided_case(hdc)
    svc = make_service([], ex=RecExec([], hris_state={}))
    result = svc.run(case, hdc, actor="hm-alex", now=NOW)
    assert result.reconciliation.status is ReconciliationStatus.PARTIAL


def test_reconciliation_failed_and_unknown():
    hdc = build_contract()
    case = decided_case(hdc)
    failed = make_service([], ex=RecExec([], status=ExecutionStatus.FAILED, mirror=False))
    assert failed.run(case, hdc, actor="hm", now=NOW).reconciliation.status is ReconciliationStatus.FAILED
    unknown = make_service([], ex=RecExec([], status=ExecutionStatus.OUTCOME_UNKNOWN, mirror=False))
    assert unknown.run(case, hdc, actor="hm", now=NOW).reconciliation.status is ReconciliationStatus.UNKNOWN


def test_reconciliation_port_is_integration_boundary_only():
    hdc = build_contract()
    case = decided_case(hdc)
    # with a reconciliation port, the record carries an external ref …
    with_port = make_service([], recon=FakeReconciliationPort()).run(case, hdc, actor="hm", now=NOW)
    assert with_port.reconciliation.external_reconciliation_ref is not None
    # … and the local status is still computed locally without a port
    without_port = make_service([]).run(case, hdc, actor="hm", now=NOW)
    assert without_port.reconciliation.external_reconciliation_ref is None
    assert without_port.reconciliation.status is ReconciliationStatus.RECONCILED


# --- standalone + invariants ---------------------------------------------
def test_spine_runs_standalone_with_fakes_only():
    hdc = build_contract()
    case = decided_case(hdc)
    svc = HiringDecisionService(action_authorization_port=RecAuth([]),
        runtime_assurance_port=RecRuntime([]), execution_port=FakeHRISExecutionPort())
    result = svc.run(case, hdc, actor="hm", now=NOW)
    assert result.receipt.execution_status is ExecutionStatus.SUCCEEDED
    for name in list(sys.modules):
        assert not name.startswith("ugence_tap_provider")
        assert not name.startswith("ugence_actiongate_provider")


def test_hris_fake_satisfies_port_protocol():
    assert isinstance(FakeHRISExecutionPort(), HRISExecutionPort)


@pytest.mark.parametrize("module", ["ugence_ai_hiring.hiring_decision.service",
                                    "ugence_ai_hiring.hiring_decision.execution"])
def test_spine_never_references_overall_fit(module):
    import importlib
    src = inspect.getsource(importlib.import_module(module))
    import_lines = [ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
    assert not any("analytics" in ln for ln in import_lines)
    assert "OverallFit" not in src and "compute_overall_fit" not in src
