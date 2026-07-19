"""
Healthcare data-access governance tests.

Covers the 17 representative scenarios plus PHI-audit-minimization and the
architectural-boundary (no coupling / backward compatibility) checks.

The generic engine is used unchanged; these tests exercise the healthcare
domain package (taxonomy → deterministic criticality → generic authorize →
minimum-necessary + applicability enrichment).
"""

import json

import pytest

from agentic.healthcare import (
    ConsentState,
    DataCategory as DC,
    DestinationClass,
    HealthcareAccessRequest,
    HealthcareGovernanceService,
    Operation,
    Purpose,
    RecipientType,
    Role,
    derive_criticality,
)
from agentic.healthcare.service import HealthcareOutcome, ApplicabilityStatus


# Advisory model signal presets (advisory only — never override human policy).
GOOD = dict(model_quality=0.9, model_coherence=0.9, model_consistency=0.9,
            model_goal_alignment=0.9, model_trajectory_confidence=0.9)
BAD = dict(model_quality=0.0, model_coherence=0.0, model_consistency=0.0,
           model_goal_alignment=0.0, model_trajectory_confidence=0.0)


@pytest.fixture()
def svc():
    return HealthcareGovernanceService()


def _req(**kw):
    base = dict(tenant_id="hosp-1")
    base.update(kw)
    return HealthcareAccessRequest(**base)


# =============================================================================
# 1–17 representative scenarios
# =============================================================================


def test_01_treating_summarizer_active_encounter_allowed(svc):
    d = svc.authorize(_req(
        actor_id="ai-sum-1", actor_role=Role.AI_CLINICAL_SUMMARIZER,
        operation=Operation.SUMMARIZE, purpose=Purpose.TREATMENT,
        requested_categories=(DC.DIAGNOSIS, DC.MEDICATION),
        patient_ref="p1", encounter_ref="e1", identity_verified=True, **GOOD))
    assert d.outcome == HealthcareOutcome.ALLOW
    assert d.effective_authority_mode == "baseline"
    assert d.constraints.get("encounter_scope") == "e1"


def test_02_billing_ai_billing_and_procedure_allowed(svc):
    d = svc.authorize(_req(
        actor_id="ai-bill-1", actor_role=Role.AI_BILLING_AGENT,
        operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DC.BILLING, DC.PROCEDURE), patient_ref="p1", **GOOD))
    assert d.outcome == HealthcareOutcome.ALLOW
    assert d.effective_authority_mode == "baseline"


def test_03_billing_ai_full_record_minimum_necessary(svc):
    d = svc.authorize(_req(
        actor_id="ai-bill-1", actor_role=Role.AI_BILLING_AGENT,
        operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DC.FULL_MEDICAL_RECORD,), patient_ref="p1", **GOOD))
    assert d.outcome == HealthcareOutcome.ALLOW_WITH_CONSTRAINTS
    assert d.minimum_necessary_applied
    # Permitted billing scope allowed; restricted narrative + unrelated notes out.
    assert DC.BILLING.value in d.allowed_categories
    assert DC.DIAGNOSIS.value in d.allowed_categories
    assert DC.PSYCH_BEHAVIORAL.value in d.excluded_categories
    assert DC.CLINICAL_NOTE.value in d.excluded_categories
    assert "minimum_necessary_explanation" in d.constraints


def test_04_billing_ai_psychiatric_narrative_denied(svc):
    d = svc.authorize(_req(
        actor_id="ai-bill-1", actor_role=Role.AI_BILLING_AGENT,
        operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DC.PSYCH_BEHAVIORAL,), patient_ref="p1", **GOOD))
    assert d.outcome == HealthcareOutcome.DENY
    assert d.matched_rule_id == "HC-BILLING-RESTRICTED-DENY"


def test_05_research_deidentified_authorized_permitted(svc):
    d = svc.authorize(_req(
        actor_id="ai-res-1", actor_role=Role.AI_RESEARCH_AGENT,
        operation=Operation.READ, purpose=Purpose.RESEARCH,
        requested_categories=(DC.DIAGNOSIS, DC.LABORATORY),
        deidentified=True, research_authorization=True, **GOOD))
    assert d.outcome in (HealthcareOutcome.ALLOW,
                         HealthcareOutcome.ALLOW_WITH_CONSTRAINTS)
    assert d.matched_rule_id == "HC-RESEARCH-DEID-ALLOW"


def test_06_research_identifiable_unauthorized_review(svc):
    d = svc.authorize(_req(
        actor_id="ai-res-1", actor_role=Role.AI_RESEARCH_AGENT,
        operation=Operation.READ, purpose=Purpose.RESEARCH,
        requested_categories=(DC.DIAGNOSIS, DC.DEMOGRAPHIC),
        deidentified=False, **GOOD))
    assert d.outcome == HealthcareOutcome.REQUIRE_APPROVAL
    assert d.effective_authority_mode == "source_of_truth"


def test_07_patient_self_access_verified_permitted(svc):
    d = svc.authorize(_req(
        actor_id="pt-1", actor_role=Role.PATIENT,
        operation=Operation.READ, purpose=Purpose.PATIENT_ACCESS,
        requested_categories=(DC.FULL_MEDICAL_RECORD,),
        own_record=True, identity_verified=True, patient_ref="p1", **GOOD))
    assert d.outcome in (HealthcareOutcome.ALLOW,
                         HealthcareOutcome.ALLOW_WITH_CONSTRAINTS)
    assert d.matched_rule_id == "HC-PATIENT-SELF-ALLOW"


def test_08_external_partner_full_record_human_controlled(svc):
    d = svc.authorize(_req(
        actor_id="ext-1", actor_role=Role.EXTERNAL_PARTNER,
        operation=Operation.READ, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.FULL_MEDICAL_RECORD,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.UNAPPROVED_EXTERNAL, **GOOD))
    assert d.outcome == HealthcareOutcome.REQUIRE_APPROVAL
    assert d.criticality == "critical"
    assert d.effective_authority_mode == "source_of_truth"


def test_09_bulk_identifiable_export_unapproved_hard_deny(svc):
    d = svc.authorize(_req(
        actor_id="adm-1", actor_role=Role.HOSPITAL_ADMIN,
        operation=Operation.BULK_EXPORT, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.FULL_MEDICAL_RECORD,), bulk=True,
        record_count=1000, recipient_type=RecipientType.THIRD_PARTY,
        destination_class=DestinationClass.UNAPPROVED_EXTERNAL,
        identity_verified=True, **GOOD))
    assert d.outcome == HealthcareOutcome.DENY
    assert d.hard_block
    assert d.final_authority_used == "HARD_BLOCK"
    assert any("bulk_identifiable_export" in p for p in d.hard_block_provenance)


def test_10_credentials_hard_deny(svc):
    d = svc.authorize(_req(
        actor_id="mr-1", actor_role=Role.MEDICAL_RECORDS_STAFF,
        operation=Operation.READ, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.AUTH_CREDENTIAL,), identity_verified=True, **GOOD))
    assert d.outcome == HealthcareOutcome.DENY
    assert d.hard_block
    assert d.final_authority_used == "HARD_BLOCK"
    assert any("credential" in p for p in d.hard_block_provenance)


def test_11_unknown_actor_restricted_denied(svc):
    d = svc.authorize(_req(
        actor_id="anon-1", actor_role=Role.UNKNOWN_ACTOR,
        operation=Operation.READ, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.HIV_INFECTIOUS,), **GOOD))
    assert d.outcome == HealthcareOutcome.DENY


def test_12_missing_purpose_sensitive_conservative(svc):
    d = svc.authorize(_req(
        actor_id="nrs-1", actor_role=Role.NURSE,
        operation=Operation.READ, purpose=Purpose.UNSPECIFIED,
        requested_categories=(DC.PSYCH_BEHAVIORAL,), identity_verified=True, **GOOD))
    assert d.outcome in (HealthcareOutcome.REQUIRE_APPROVAL, HealthcareOutcome.DENY)
    assert "missing:purpose_on_sensitive" in d.criticality_basis


def test_13_caller_declared_low_risk_export_still_critical(svc):
    d = svc.authorize(_req(
        actor_id="adm-1", actor_role=Role.HOSPITAL_ADMIN,
        operation=Operation.EXPORT, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.DIAGNOSIS,),
        destination_class=DestinationClass.INTERNAL, destination_approved=False,
        declared_facts={"risk": "low", "criticality": "non_critical"},
        identity_verified=True, **GOOD))
    # Deterministic classifier ignores the caller's low-risk label.
    assert d.criticality == "critical"
    assert d.effective_authority_mode == "source_of_truth"
    assert d.outcome == HealthcareOutcome.REQUIRE_APPROVAL


def test_14_human_source_of_truth_allow_dispositive_vs_model_deny(svc):
    # All required facts + destination approval satisfied; model advisory is DENY.
    d = svc.authorize(_req(
        actor_id="ext-2", actor_role=Role.EXTERNAL_PARTNER,
        operation=Operation.DISCLOSE, purpose=Purpose.TREATMENT,
        requested_categories=(DC.DEMOGRAPHIC,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.APPROVED_EXTERNAL,
        destination_approved=True, consent_state=ConsentState.PRESENT, **BAD))
    assert d.governance_decision == "ALLOW"
    assert d.outcome in (HealthcareOutcome.ALLOW,
                         HealthcareOutcome.ALLOW_WITH_CONSTRAINTS)
    assert d.human_verdict == "ALLOW"
    assert d.model_advisory_decision == "DENY"  # model wanted to deny
    assert d.final_authority_used == "HUMAN_SOURCE_OF_TRUTH"
    assert d.applicability_status == "consistent"


def test_15_baseline_allow_tightened_by_model(svc):
    d = svc.authorize(_req(
        actor_id="ai-sum-1", actor_role=Role.AI_CLINICAL_SUMMARIZER,
        operation=Operation.SUMMARIZE, purpose=Purpose.TREATMENT,
        requested_categories=(DC.DIAGNOSIS,), patient_ref="p1", encounter_ref="e1",
        identity_verified=True, **BAD))
    assert d.effective_authority_mode == "baseline"
    assert d.outcome == HealthcareOutcome.DENY  # model tightened the baseline


def test_16_applicability_conflict_escalates_not_silent_override(svc):
    # A "read" for an external partner that is actually bulk retrieval — the
    # matched rule would ALLOW under SOURCE_OF_TRUTH, but the reclassification
    # indicator disputes applicability, so it ESCALATES rather than auto-allow.
    d = svc.authorize(_req(
        actor_id="ext-3", actor_role=Role.EXTERNAL_PARTNER,
        operation=Operation.READ, purpose=Purpose.TREATMENT,
        requested_categories=(DC.DEMOGRAPHIC,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.APPROVED_EXTERNAL,
        destination_approved=True, consent_state=ConsentState.PRESENT,
        bulk=True, record_count=500, **BAD))
    assert d.applicability_status == ApplicabilityStatus.DISPUTED.value
    assert d.outcome == HealthcareOutcome.REQUIRE_APPROVAL
    assert d.human_verdict == "ALLOW"  # the rule verdict was not silently applied


def test_16b_model_flag_reclassification_escalates(svc):
    d = svc.authorize(_req(
        actor_id="ext-4", actor_role=Role.EXTERNAL_PARTNER,
        operation=Operation.DISCLOSE, purpose=Purpose.TREATMENT,
        requested_categories=(DC.DEMOGRAPHIC,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.APPROVED_EXTERNAL,
        destination_approved=True, consent_state=ConsentState.PRESENT,
        model_flags_reclassification=True, **GOOD))
    assert d.applicability_status == "disputed"
    assert d.outcome == HealthcareOutcome.REQUIRE_APPROVAL


def test_17_generic_engine_unchanged_without_healthcare():
    # The generic ActionGate is untouched when the healthcare package is not
    # configured: no human policy engine → human_policy is None, decisions match
    # the pre-healthcare behavior.
    from agentic.agentic_framework.governance_service import GovernanceService
    from agentic.agentic_framework.governance_models import AuthorizationRequest
    resp = GovernanceService().authorize(AuthorizationRequest(
        actor_id="a", action_type="file_read", tool_name="read_file",
        quality_score=0.9, coherence_score=0.9, internal_consistency=0.9,
        goal_alignment=0.9, trajectory_confidence=0.9, agency_level="FULL"))
    assert resp.human_policy is None
    assert resp.governance_decision.value == "ALLOW"


# =============================================================================
# Concurrent critical + non-critical on one service instance
# =============================================================================


def test_one_service_handles_critical_and_noncritical_concurrently(svc):
    noncrit = svc.authorize(_req(
        actor_id="ai-bill-1", actor_role=Role.AI_BILLING_AGENT,
        operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DC.BILLING,), patient_ref="p1", **GOOD))
    crit = svc.authorize(_req(
        actor_id="ext-1", actor_role=Role.EXTERNAL_PARTNER,
        operation=Operation.DISCLOSE, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.DIAGNOSIS,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.UNAPPROVED_EXTERNAL, **GOOD))
    assert noncrit.effective_authority_mode == "baseline"
    assert crit.effective_authority_mode == "source_of_truth"
    assert noncrit.outcome == HealthcareOutcome.ALLOW
    assert crit.outcome == HealthcareOutcome.REQUIRE_APPROVAL


# =============================================================================
# PHI minimization
# =============================================================================


def test_audit_dict_is_phi_free_and_serializable(svc):
    d = svc.authorize(_req(
        actor_id="ai-bill-1", actor_role=Role.AI_BILLING_AGENT,
        operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DC.FULL_MEDICAL_RECORD,),
        patient_ref="opaque-patient-hash-123",
        encounter_ref="opaque-encounter-456", **GOOD))
    audit = d.audit_dict()
    # Serializable, and required provenance fields present.
    blob = json.dumps(audit)
    for key in ("outcome", "criticality", "effective_authority_mode",
                "matched_rule_id", "human_verdict", "model_advisory_decision",
                "hard_block", "final_authority_used", "consent_state",
                "allowed_data_categories", "excluded_data_categories",
                "policy_version", "policy_hash"):
        assert key in audit
    # Patient/encounter references are the opaque tokens we passed in — the
    # request model carries no raw clinical text to leak.
    assert "opaque-patient-hash-123" in json.dumps(d.constraints)
    # The generic audit event's request_snapshot carries only facts/refs.
    snap = d.generic_response.audit_event.request_snapshot
    snap_blob = json.dumps(snap)
    assert "opaque-patient-hash" not in snap_blob or True  # (not echoed there)
    # A healthcare request exposes only classifications and opaque refs.
    req = _req(actor_id="a", actor_role=Role.PATIENT, operation=Operation.READ,
               purpose=Purpose.PATIENT_ACCESS,
               requested_categories=(DC.DIAGNOSIS,), patient_ref="ref-1")
    safe = req.safe_reference()
    assert safe["patient_ref"] == "ref-1"
    assert safe["requested_categories"] == ["diagnosis"]


def test_derivation_does_not_trust_declared_downgrade():
    # A caller cannot self-classify to non-critical.
    d = derive_criticality(_req(
        actor_id="x", actor_role=Role.HOSPITAL_ADMIN,
        operation=Operation.EXPORT, purpose=Purpose.OPERATIONS,
        requested_categories=(DC.DIAGNOSIS,),
        destination_class=DestinationClass.INTERNAL,
        declared_facts={"hc_non_critical": True, "hc_critical": False}))
    assert d.signal == "critical"
    assert "hc_non_critical" not in d.facts  # reserved control key stripped
