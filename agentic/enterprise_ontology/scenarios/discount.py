"""Scenario A — customer discount / pricing exception (Sales vs Finance/Legal/Ops/IT)."""

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
        # Purpose: Sales wants conversion (declared, advisory) vs Finance margin (authoritative)
        rec("p_sales", L.PURPOSE, V.SALES, {"objective": "increase_conversion"},
            origin=EO.SUPPLIED, verify=VS.DECLARED, authority=AR.ADVISORY),
        rec("p_fin", L.PURPOSE, V.FINANCE,
            {"objective": "preserve_margin", "margin_floor": 0.15},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING, policy_refs=("FIN-MARGIN-POLICY",)),
        rec("id_sales", L.IDENTITY, V.SALES, "sales_agent:jdoe",
            verify=VS.VERIFIED, authority=AR.SUPPORTING_EVIDENCE),
        # Agency: discounts >15% require VP Finance sign-off (authoritative requirement)
        rec("ag_fin", L.AGENCY, V.FINANCE,
            {"required_approver": "VP_Finance", "threshold": 0.15},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING, policy_refs=("FIN-APPROVAL-MATRIX",)),
        rec("r_fin", L.REASONING, V.FINANCE, "20% discount → 12% margin < 15% floor",
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING),
        rec("core_fin", L.CORE, V.FINANCE,
            {"invariant": "margin_floor", "preserved": False},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING, reason="MARGIN_FLOOR_BREACH"),
        rec("uni_fin", L.UNIVERSAL, V.FINANCE,
            {"constraint": "quarterly_margin_precedent", "breached": True},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.INFERRED,
            authority=AR.SUPPORTING_EVIDENCE),
    )
    decisions = (
        # Sales "approves" citing ONLY its own advisory purpose + identity.
        VerticalDecision(
            "d_sales", V.SALES, DecisionEffect.ALLOW,
            "Approve 20% discount", supporting_record_ids=("p_sales", "id_sales"),
            reason_code="SALES_DISCOUNT_APPROVED"),
    )
    executions = (
        ExecutionRecord("ex_crm", V.IT, "CRM", "quote:Q1",
                        authorized_form="quote", executed_form="contract",
                        resulting_state={"discount": 0.20, "price": 80}),
        ExecutionRecord("ex_erp", V.FINANCE, "ERP", "quote:Q1",
                        authorized_form="quote", executed_form="quote",
                        resulting_state={"discount": 0.0, "price": 100}),
    )
    dependencies = (
        VerticalDependency(V.SALES, V.FINANCE, "ag_fin", DependencyStatus.ABSENT,
                           "discount >15% needs VP Finance approval"),
    )
    env = EnterpriseEventEnvelope(
        "evt-discount-1", "pricing_exception", records, dependencies, decisions,
        executions, reconciliation_status="failed")

    baseline = (
        B(V.SALES, "discount_proposed", "approved", {"pct": 0.20}),
        # Finance's own margin system can flag its local breach:
        B(V.FINANCE, "margin_check", "violation", {"margin": 0.12},
          local_flag=F.CORE_INVARIANT_BREACH),
        B(V.IT, "crm_quote_update", "done", {"form": "contract"}),
        B(V.FINANCE, "erp_price", "unchanged", {"price": 100}),
    )
    return Scenario(
        "discount", "20% discount proposed by Sales; margin/authority/reconciliation.",
        env, baseline,
        expected_failure_classes=frozenset({
            F.MISSING_AUTHORITY_BASIS, F.ADVISORY_AUTHORITY_ESCALATION,
            F.MISSING_VERIFIED_PURPOSE, F.PURPOSE_POLICY_VIOLATION,
            F.FORM_EXECUTION_MISMATCH, F.CROSS_VERTICAL_DEPENDENCY_FAILURE,
            F.CORE_INVARIANT_BREACH, F.UNIVERSAL_CONSTRAINT_BREACH,
            F.STATE_RECONCILIATION_FAILURE,
        }))
