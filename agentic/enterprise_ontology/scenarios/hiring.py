"""Scenario D — employee hiring & onboarding (HR/Finance/Legal/IT/Security/Payroll)."""

from __future__ import annotations

from agentic.enterprise_ontology.events import (
    DecisionEffect, DependencyStatus, EnterpriseEventEnvelope, ExecutionRecord,
    VerticalDecision, VerticalDependency,
)
from agentic.enterprise_ontology.failure_classes import FailureClass as F
from agentic.enterprise_ontology.projection import BaselineWorkflowRecord as B, Scenario
from agentic.enterprise_ontology.scenarios._helpers import AR, EO, L, ST, V, VS, rec


def build() -> Scenario:
    records = (
        rec("p_hr", L.PURPOSE, V.HR, {"objective": "approved_headcount", "req": "REQ-9"},
            verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING,
            policy_refs=("HR-HEADCOUNT",)),
        # Candidate identity NOT yet verified, but HR proceeds.
        rec("id_hr", L.IDENTITY, V.HR, "candidate:alex",
            origin=EO.SUPPLIED, verify=VS.UNKNOWN, authority=AR.SUPPORTING_EVIDENCE,
            reason="IDENTITY_UNVERIFIED"),
        # IT provisioning cites only the HR request (not an authority-bearing record).
        rec("hr_request", L.EXECUTION, V.HR, {"request": "provision_access"},
            verify=VS.DECLARED, authority=AR.SUPPORTING_EVIDENCE),
    )
    decisions = (
        VerticalDecision(
            "d_hire", V.HR, DecisionEffect.ALLOW, "Proceed to onboarding",
            supporting_record_ids=("p_hr",), reason_code="HIRE_APPROVED"),
        VerticalDecision(
            "d_it", V.IT, DecisionEffect.ALLOW, "Provision access",
            supporting_record_ids=("hr_request",), reason_code="ACCESS_GRANTED"),
    )
    executions = (
        ExecutionRecord("ex_iam", V.IT, "IAM", "employee:E1",
                        authorized_form="standard_access", executed_form="admin_access",
                        resulting_state={"access": True, "level": "admin"}),
        ExecutionRecord("ex_hr", V.HR, "HRIS", "employee:E1",
                        authorized_form="standard_access", executed_form="standard_access",
                        resulting_state={"onboarded": False}),
        ExecutionRecord("ex_pay", V.PAYROLL, "Payroll", "employee:E1",
                        authorized_form=None, executed_form=None,
                        resulting_state={"active": True}),
    )
    dependencies = (
        VerticalDependency(V.IT, V.HR, "id_hr", DependencyStatus.PENDING,
                           "identity verification before access"),
    )
    env = EnterpriseEventEnvelope(
        "evt-hire-1", "employee_onboarding", records, dependencies, decisions,
        executions, reconciliation_status="failed")

    baseline = (
        B(V.HR, "offer_accepted", "done", {}),
        B(V.IT, "access_provisioned", "done", {"level": "admin"}),
        B(V.PAYROLL, "activated", "done", {}),
    )
    return Scenario(
        "hiring", "Onboarding: access before identity verification; multi-system state.",
        env, baseline,
        expected_failure_classes=frozenset({
            F.IDENTITY_AUTHORITY_VIOLATION, F.MISSING_AUTHORITY_BASIS,
            F.ADVISORY_AUTHORITY_ESCALATION, F.FORM_EXECUTION_MISMATCH,
            F.CROSS_VERTICAL_DEPENDENCY_FAILURE, F.STATE_RECONCILIATION_FAILURE,
        }))
