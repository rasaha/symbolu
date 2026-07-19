"""Scenario C — procurement / vendor purchase (Dept/Procurement/Finance/Legal/Security/IT).

Deliberately CLEAN on identity/authority/purpose/advisory — the value here is
Universal (cumulative vendor concentration), a stale cross-vertical dependency,
execution-vs-observation, and multi-system reconciliation. This shows the
ontology does not over-flag: different scenarios exercise different invariants.
"""

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
        rec("p_dept", L.PURPOSE, V.REQUESTING_DEPT, {"objective": "analytics_tooling"},
            verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING,
            policy_refs=("PROC-NEED-JUSTIFICATION",)),
        rec("ag_fin", L.AGENCY, V.FINANCE, {"approved_budget": 60000},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING),
        rec("sec_risk", L.REASONING, V.SECURITY, {"vendor_risk": "assessment_stale"},
            origin=EO.OBSERVED, verify=VS.DISPUTED, authority=AR.SUPPORTING_EVIDENCE),
        rec("uni_sec", L.UNIVERSAL, V.SECURITY,
            {"constraint": "vendor_concentration", "breached": True,
             "share": 0.42, "limit": 0.30},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING),
        # Independent observation disagrees with the PO system's recorded amount.
        rec("obs_po", L.OBSERVATION, V.FINANCE, {"amount": 58000},
            origin=EO.OBSERVED, verify=VS.VERIFIED, authority=AR.SUPPORTING_EVIDENCE),
    )
    decisions = (
        # Authority basis present (Finance budget) — no authority failure expected.
        VerticalDecision(
            "d_proc", V.PROCUREMENT, DecisionEffect.ALLOW,
            "Approve vendor purchase", supporting_record_ids=("p_dept", "ag_fin"),
            reason_code="PO_APPROVED"),
    )
    executions = (
        ExecutionRecord("ex_po", V.PROCUREMENT, "PO_System", "po:PO1",
                        authorized_form="purchase_order", executed_form="purchase_order",
                        resulting_state={"amount": 60000}, observation_ref="obs_po"),
        ExecutionRecord("ex_inv", V.FINANCE, "Invoicing", "po:PO1",
                        authorized_form="purchase_order", executed_form="purchase_order",
                        resulting_state={"amount": 75000}),  # invoice > PO
    )
    dependencies = (
        VerticalDependency(V.PROCUREMENT, V.SECURITY, "sec_risk", DependencyStatus.STALE,
                           "vendor security assessment"),
    )
    env = EnterpriseEventEnvelope(
        "evt-procure-1", "vendor_purchase", records, dependencies, decisions,
        executions, reconciliation_status="failed")

    baseline = (
        B(V.PROCUREMENT, "po_approved", "ok", {"amount": 60000}),
        B(V.SECURITY, "vendor_risk", "stale", {},
          local_flag=F.STALE_OR_CONFLICTING_EVIDENCE),
        B(V.FINANCE, "invoice", "posted", {"amount": 75000}),
    )
    return Scenario(
        "procurement", "Vendor PO: cumulative concentration, stale security, invoice mismatch.",
        env, baseline,
        expected_failure_classes=frozenset({
            F.UNIVERSAL_CONSTRAINT_BREACH, F.CROSS_VERTICAL_DEPENDENCY_FAILURE,
            F.STALE_OR_CONFLICTING_EVIDENCE, F.STATE_RECONCILIATION_FAILURE,
            F.EXECUTION_OBSERVATION_MISMATCH,
        }))
