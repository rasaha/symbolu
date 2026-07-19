"""Four targeted stage-2 scenarios (violating + clean), one per concept."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Tuple

from agentic.enterprise_ontology.events import (
    DecisionEffect, EnterpriseEventEnvelope, ExecutionRecord, VerticalDecision,
)
from agentic.enterprise_ontology.layers import OntologyLayer as L
from agentic.enterprise_ontology.scenarios._helpers import AR, EO, ST, V, VS, rec
from agentic.enterprise_ontology.stage2.evidence import (
    CognitionEvidence, IntegrationEvidence, PotentialEvidence, ReasoningEvidence,
    StateAssertion, StateConflict,
)
from agentic.enterprise_ontology.stage2.failures import (
    Concept, Stage2FailureClass as FC,
)


@dataclass(frozen=True)
class Stage2Scenario:
    concept: Concept
    name: str
    description: str
    violating: EnterpriseEventEnvelope
    clean: EnterpriseEventEnvelope
    expected: FrozenSet[FC]
    baseline_reproducible: FrozenSet[FC]  # what request-time / stage-1 baseline gets


def _cog(rid, vertical, model, ver, stance, conf, unc, rationale, approval):
    return rec(rid, L.COGNITION, vertical,
               CognitionEvidence(model, ver, stance, conf, unc, rationale, approval),
               origin=EO.DERIVED_INTERPRETIVE, verify=VS.INFERRED, authority=AR.ADVISORY)


# --- Scenario 1: Potential ---------------------------------------------------

def potential_scenario() -> Stage2Scenario:
    pe = PotentialEvidence(
        available_capabilities=("deploy_dev", "deploy_staging", "deploy_production",
                                "privileged_maintenance", "deploy_dr_legacy"),
        permitted_capabilities=("deploy_dev", "deploy_staging"),
        prohibited_capabilities=("privileged_maintenance",),
        reachable_plan_branches=("deploy_production", "deploy_partner_env"),
        revoked_capabilities=("deploy_dr_legacy",),
        approval_required_capabilities=("deploy_production",),
        approvals_present=())
    violating = EnterpriseEventEnvelope(
        "s2-potential", "capability_space",
        (rec("pot", L.POTENTIAL, V.IT, pe, authority=AR.SUPPORTING_EVIDENCE),))
    clean_pe = PotentialEvidence(
        available_capabilities=("deploy_dev", "deploy_staging"),
        permitted_capabilities=("deploy_dev", "deploy_staging"),
        prohibited_capabilities=("privileged_maintenance",),
        approval_required_capabilities=("deploy_production",))
    clean = EnterpriseEventEnvelope(
        "s2-potential-clean", "capability_space",
        (rec("pot", L.POTENTIAL, V.IT, clean_pe, authority=AR.SUPPORTING_EVIDENCE),))
    return Stage2Scenario(
        Concept.POTENTIAL, "potential_deploy",
        "IT deploy agent's reachable action space contains prohibited / revoked / "
        "approval-required / unpermitted branches before any request.",
        violating, clean,
        expected=frozenset({FC.PROHIBITED_CAPABILITY_EXPOSURE, FC.STALE_CAPABILITY_STATE,
                            FC.POTENTIAL_AUTHORITY_MISMATCH, FC.UNAUTHORIZED_PLAN_BRANCH}),
        baseline_reproducible=frozenset())  # request-time governance sees nothing pre-action


# --- Scenario 2: Cognition ---------------------------------------------------

def cognition_scenario() -> Stage2Scenario:
    records = (
        _cog("cog_mkt", V.MARKETING, "mkt_forecaster", "3.1", "expand", 0.9, 0.1, "r1", "approved"),
        _cog("cog_fin", V.FINANCE, "margin_model", "2.0", "do_not_expand", 0.6, 0.3, "r2", "approved"),
        _cog("cog_sales", V.SALES, "pipeline_model", "1.4", "expand", 0.3, 0.5, "r3", "approved"),
        _cog("cog_priv", V.PRIVACY, "consent_risk_model", "0.9", "caution", 0.85, 0.6, None, "unapproved"),
    )
    # Marketing decides to expand, resting SOLELY on Privacy's unapproved advisory.
    decisions = (VerticalDecision("d_expand", V.MARKETING, DecisionEffect.ALLOW,
                                  "Expand campaign", supporting_record_ids=("cog_priv",),
                                  reason_code="CAMPAIGN_EXPAND"),)
    violating = EnterpriseEventEnvelope("s2-cognition", "campaign_expansion", records,
                                        decisions=decisions)
    clean_records = (
        _cog("cog_mkt", V.MARKETING, "mkt_forecaster", "3.1", "expand", 0.9, 0.1, "r1", "approved"),
        _cog("cog_fin", V.FINANCE, "margin_model", "2.0", "expand", 0.8, 0.2, "r2", "approved"),
    )
    auth = rec("auth", L.AGENCY, V.MARKETING, {"approved": True},
               origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING)
    clean = EnterpriseEventEnvelope(
        "s2-cognition-clean", "campaign_expansion", clean_records + (auth,),
        decisions=(VerticalDecision("d_expand", V.MARKETING, DecisionEffect.ALLOW,
                                    "Expand", supporting_record_ids=("auth",)),))
    return Stage2Scenario(
        Concept.COGNITION, "cognition_conflict",
        "Four models disagree; a vertical relies solely on another vertical's "
        "unapproved advisory model as decision basis.",
        violating, clean,
        expected=frozenset({FC.ADVISORY_CONFLICT, FC.CONFIDENCE_PROVENANCE_GAP,
                            FC.ADVISORY_AUTHORITY_ESCALATION, FC.UNAPPROVED_MODEL_RELIANCE,
                            FC.COGNITIVE_SOURCE_MISMATCH}),
        baseline_reproducible=frozenset({FC.ADVISORY_AUTHORITY_ESCALATION}))


# --- Scenario 3: Reasoning ---------------------------------------------------

def reasoning_scenario() -> Stage2Scenario:
    records = (
        rec("re_sales", L.REASONING, V.SALES, ReasoningEvidence(
            "d_discount", ("R-COMM-12",), ("commercial@2.0",),
            ("approve<-list_price", "list_price<-catalog"), (), ())),
        rec("re_fin", L.REASONING, V.FINANCE, ReasoningEvidence(
            "d_discount", ("R-MARGIN-3",), ("margin@1.0",),   # STALE version
            ("m<-n", "n<-m"), ("LEGACY-EX",), ())),            # cyclic derivation
        rec("re_legal", L.REASONING, V.LEGAL, ReasoningEvidence(
            "d_discount", ("R-REGION-7",), ("margin@2.0",),   # current version
            ("approve<-region_exception",), ("REGION-EX-EU",), ())),
        rec("re_exec", L.REASONING, V.EXECUTIVE, ReasoningEvidence(
            "d_discount", (), (), (), (), ("EXEC-OVERRIDE-9",))),  # override, no derivation
        rec("re_ops", L.REASONING, V.OPERATIONS, ReasoningEvidence(
            "d_discount", (), ("ops@1.0",), ("x<-y",), (), ("OV-2",))),  # override + deriv, no rules
    )
    violating = EnterpriseEventEnvelope("s2-reasoning", "discount_paths", records)
    clean = EnterpriseEventEnvelope("s2-reasoning-clean", "discount_paths", (
        rec("re_sales", L.REASONING, V.SALES, ReasoningEvidence(
            "d_discount", ("R-COMM-12",), ("commercial@2.0", "margin@2.0"),
            ("approve<-list_price",), (), ())),
        rec("re_fin", L.REASONING, V.FINANCE, ReasoningEvidence(
            "d_discount", ("R-MARGIN-3",), ("margin@2.0",), ("approve<-margin_ok",), (), ())),
    ))
    return Stage2Scenario(
        Concept.REASONING, "reasoning_incoherent_paths",
        "Verticals reach the same permissive outcome via conflicting policy "
        "versions, incompatible exceptions, an unjustified override, and a "
        "circular derivation.",
        violating, clean,
        expected=frozenset({FC.POLICY_VERSION_CONFLICT, FC.INCOMPATIBLE_RULE_BASIS,
                            FC.UNJUSTIFIED_OVERRIDE, FC.DERIVATION_CHAIN_FAILURE,
                            FC.REASONING_PROVENANCE_GAP}),
        baseline_reproducible=frozenset())  # flat policy_refs cannot express these


# --- Scenario 4: Integration -------------------------------------------------

def integration_scenario() -> Stage2Scenario:
    ie = IntegrationEvidence(
        intended_final_state=(
            StateAssertion("CRM", "effective_date", "2026-01-01"),
            StateAssertion("ERP", "effective_date", "2026-01-01"),
            StateAssertion("Billing", "invoice_schedule", "created"),
            StateAssertion("Finance", "credit_hold", "released"),
        ),
        observed_final_state=(
            StateAssertion("CRM", "effective_date", "2026-01-01"),
            StateAssertion("ERP", "effective_date", "2026-02-01"),   # conflict
            # Billing invoice_schedule MISSING → incomplete transition
            StateAssertion("Finance", "credit_hold", "on_hold"),      # conflict
        ),
        unresolved_conflicts=(
            StateConflict("forecast", ("RevenueForecast", "CashForecast"),
                          ("includes_deal", "excludes_deal"),
                          "deal in revenue forecast but not cash forecast"),
        ),
        required_closure_conditions=("invoice_schedule_created", "credit_hold_released",
                                     "effective_dates_aligned"),
        satisfied_closure_conditions=(),
        marked_complete=True)  # event marked complete prematurely
    # Executions mirror the CRM/ERP date disagreement so stage-1 reconciliation can
    # catch the EXISTENCE of a problem (for the metadata-reproduction comparison).
    executions = (
        ExecutionRecord("ex_crm", V.SALES, "CRM", "contract:K1", None, None,
                        {"effective": "2026-01-01"}),
        ExecutionRecord("ex_erp", V.FINANCE, "ERP", "contract:K1", None, None,
                        {"effective": "2026-02-01"}),
    )
    violating = EnterpriseEventEnvelope(
        "s2-integration", "contract_activation",
        (rec("intg", L.INTEGRATION, V.OPERATIONS, ie, authority=AR.SUPPORTING_EVIDENCE),),
        executions=executions, reconciliation_status="complete")
    clean_ie = IntegrationEvidence(
        intended_final_state=(StateAssertion("CRM", "effective_date", "2026-01-01"),),
        observed_final_state=(StateAssertion("CRM", "effective_date", "2026-01-01"),),
        required_closure_conditions=("effective_dates_aligned",),
        satisfied_closure_conditions=("effective_dates_aligned",),
        marked_complete=True)
    clean = EnterpriseEventEnvelope(
        "s2-integration-clean", "contract_activation",
        (rec("intg", L.INTEGRATION, V.OPERATIONS, clean_ie, authority=AR.SUPPORTING_EVIDENCE),),
        reconciliation_status="complete")
    return Stage2Scenario(
        Concept.INTEGRATION, "integration_incoherent_state",
        "Every local action succeeded but the enterprise final state is "
        "inconsistent and the event was marked complete prematurely.",
        violating, clean,
        expected=frozenset({FC.CROSS_SYSTEM_STATE_CONFLICT,
                            FC.INCOMPLETE_ENTERPRISE_TRANSITION,
                            FC.PREMATURE_EVENT_CLOSURE}),
        baseline_reproducible=frozenset({FC.STATE_RECONCILIATION_FAILURE}))


def all_stage2_scenarios():
    return [potential_scenario(), cognition_scenario(),
            reasoning_scenario(), integration_scenario()]
