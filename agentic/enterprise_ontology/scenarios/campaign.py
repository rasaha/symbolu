"""Scenario B — marketing campaign launch (Marketing/Finance/Privacy/IT/Security/Ops)."""

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
        rec("p_mkt", L.PURPOSE, V.MARKETING, {"objective": "increase_pipeline"},
            verify=VS.DECLARED, authority=AR.ADVISORY),
        rec("core_priv", L.CORE, V.PRIVACY,
            {"invariant": "audience_data_use_consent", "preserved": False},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING, policy_refs=("PRIV-CONSENT-POLICY",),
            reason="CONSENT_ABSENT"),
        rec("ag_fin", L.AGENCY, V.FINANCE, {"approved_budget": 50000},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING),
        rec("uni_fin", L.UNIVERSAL, V.FINANCE,
            {"constraint": "quarterly_marketing_budget", "breached": True},
            origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED,
            authority=AR.AUTHORITY_BEARING),
        rec("cog_mkt", L.COGNITION, V.MARKETING,
            {"predicted_ctr": 0.04, "anomaly": 0.1}, origin=EO.DERIVED_INTERPRETIVE,
            verify=VS.INFERRED, authority=AR.ADVISORY, confidence=0.6),
    )
    decisions = (
        VerticalDecision(
            "d_mkt", V.MARKETING, DecisionEffect.ALLOW,
            "Launch campaign", supporting_record_ids=("p_mkt", "cog_mkt"),
            reason_code="CAMPAIGN_LAUNCH"),
    )
    executions = (
        ExecutionRecord("ex_ads", V.MARKETING, "AdPlatform", "campaign:C1",
                        authorized_form="opt_in_email", executed_form="cold_email",
                        resulting_state={"launched": True, "audience": 100000}),
        ExecutionRecord("ex_crm", V.SALES, "CRM", "campaign:C1",
                        authorized_form="opt_in_email", executed_form="opt_in_email",
                        resulting_state={"launched": False, "audience": 0}),
    )
    dependencies = (
        VerticalDependency(V.MARKETING, V.PRIVACY, "core_priv", DependencyStatus.DENIED,
                           "audience data-use consent"),
        VerticalDependency(V.MARKETING, V.IT, None, DependencyStatus.PENDING,
                           "campaign infrastructure readiness"),
    )
    env = EnterpriseEventEnvelope(
        "evt-campaign-1", "campaign_launch", records, dependencies, decisions,
        executions, reconciliation_status="failed")

    baseline = (
        B(V.MARKETING, "campaign_launch", "launched", {"audience": 100000}),
        B(V.PRIVACY, "consent_check", "missing", {},
          local_flag=F.CORE_INVARIANT_BREACH),
        B(V.FINANCE, "budget_check", "ok", {"budget": 50000}),
        B(V.IT, "infra", "provisioning", {}),
    )
    return Scenario(
        "campaign", "Campaign launched without consent / budget / IT readiness.",
        env, baseline,
        expected_failure_classes=frozenset({
            F.MISSING_AUTHORITY_BASIS, F.ADVISORY_AUTHORITY_ESCALATION,
            F.MISSING_VERIFIED_PURPOSE, F.CORE_INVARIANT_BREACH,
            F.UNIVERSAL_CONSTRAINT_BREACH, F.CROSS_VERTICAL_DEPENDENCY_FAILURE,
            F.FORM_EXECUTION_MISMATCH, F.STATE_RECONCILIATION_FAILURE,
        }))
