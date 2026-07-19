"""
Healthcare enforcement + adversarial validation.

Proves ActionGate constraints are actually enforced between authorization and
simulated HIS/EMR retrieval — and cannot be ignored, widened, replayed, or
bypassed. All records are synthetic. Required leakage count is ZERO.
"""

import json

import pytest

from agentic.healthcare import (
    DataCategory as DC,
    HealthcareAccessRequest,
    Operation,
    Purpose,
    Role,
    derive_criticality,
)
from agentic.healthcare.taxonomy import ConsentState, DestinationClass, RecipientType
from agentic.healthcare.policy import build_healthcare_criticality_registry
from agentic.agentic_framework.human_policy import CriticalityClass, RequestContext
from agentic.healthcare.enforcement import (
    EnforcementConfig,
    EnforcementHarness,
    ExecutionRequest,
    FixedClock,
    MismatchCode,
    SYNTHETIC_CREDENTIAL_SENTINEL,
)
from agentic.healthcare.enforcement.emr import SYNTHETIC_INJECTION

GOOD = dict(model_quality=0.9, model_coherence=0.9, model_consistency=0.9,
            model_goal_alignment=0.9, model_trajectory_confidence=0.9)
BAD = dict(model_quality=0.0, model_coherence=0.0, model_consistency=0.0,
           model_goal_alignment=0.0, model_trajectory_confidence=0.0)

RESTRICTED_VALUES = {DC.PSYCH_BEHAVIORAL.value, DC.REPRODUCTIVE_HEALTH.value,
                     DC.HIV_INFECTIOUS.value, DC.GENOMIC.value}


def _harness(**cfg):
    clock = FixedClock()
    h = EnforcementHarness(clock=clock, config=EnforcementConfig(**cfg))
    h._clock = clock
    return h


def _billing_full_record(**over):
    base = dict(
        tenant_id="hosp-A", actor_id="ai-bill", actor_role=Role.AI_BILLING_AGENT,
        agent_id="agent-x", operation=Operation.READ, purpose=Purpose.PAYMENT,
        requested_categories=(DC.FULL_MEDICAL_RECORD,), patient_ref="patient-001",
        encounter_ref="enc-1", **GOOD)
    base.update(over)
    return HealthcareAccessRequest(**base)


def _summarizer_read(**over):
    base = dict(
        tenant_id="hosp-A", actor_id="ai-sum", actor_role=Role.AI_CLINICAL_SUMMARIZER,
        agent_id="agent-sum", operation=Operation.SUMMARIZE, purpose=Purpose.TREATMENT,
        requested_categories=(DC.DIAGNOSIS, DC.MEDICATION, DC.CLINICAL_NOTE),
        patient_ref="patient-001", encounter_ref="enc-1", identity_verified=True,
        **GOOD)
    base.update(over)
    return HealthcareAccessRequest(**base)


# =============================================================================
# 1. Permitted subset only
# =============================================================================


def test_01_billing_gets_permitted_fields_not_psych():
    h = _harness()
    dec, art, res = h.run(_billing_full_record())
    assert res.executed
    assert DC.BILLING.value in res.receipt.categories_released
    assert DC.PSYCH_BEHAVIORAL.value not in res.payload
    assert DC.PSYCH_BEHAVIORAL.value in res.receipt.categories_excluded
    # No restricted or credential value ever appears in the payload.
    assert not any(k in RESTRICTED_VALUES for k in res.payload)
    assert SYNTHETIC_CREDENTIAL_SENTINEL not in json.dumps(res.payload)


def test_02_cannot_widen_billing_to_full_record():
    h = _harness()
    _, art, _ = h.run(_billing_full_record())
    # Attempt to widen at execution to the psychiatric narrative.
    res = h.execute(art, ExecutionRequest.faithful_from(
        art, requested_categories=(DC.PSYCH_BEHAVIORAL.value,)))
    assert res.denial_code == MismatchCode.SCOPE_WIDENING.value
    assert res.payload == {}


def test_03_summarize_authorization_cannot_be_reused_for_export():
    h = _harness()
    _, art, _ = h.run(_summarizer_read())
    res = h.execute(art, ExecutionRequest.faithful_from(art, operation="EXPORT"))
    assert res.denial_code == MismatchCode.OPERATION_MISMATCH.value


def test_04_internal_authorization_cannot_go_external():
    h = _harness()
    _, art, _ = h.run(_summarizer_read())
    res = h.execute(art, ExecutionRequest.faithful_from(
        art, destination_class="approved_external"))
    assert res.denial_code == MismatchCode.DESTINATION_MISMATCH.value


def test_05_patient_specific_cannot_be_replayed_against_other_patient():
    h = _harness()
    _, art, _ = h.run(_billing_full_record())
    res = h.execute(art, ExecutionRequest.faithful_from(art, patient_ref="patient-002"))
    assert res.denial_code == MismatchCode.PATIENT_MISMATCH.value


def test_06_encounter_specific_cannot_access_historical_encounter():
    h = _harness()
    _, art, _ = h.run(_summarizer_read())  # bound to enc-1
    res = h.execute(art, ExecutionRequest.faithful_from(art, encounter_ref="enc-2"))
    assert res.denial_code == MismatchCode.ENCOUNTER_MISMATCH.value


def test_07_tenant_isolation_hospital_a_cannot_access_hospital_b():
    h = _harness()
    _, art, _ = h.run(_billing_full_record())
    res = h.execute(art, ExecutionRequest.faithful_from(art, tenant_id="hosp-B"))
    assert res.denial_code == MismatchCode.TENANT_MISMATCH.value


def test_08_authorization_bound_to_agent_cannot_be_used_by_another():
    h = _harness()
    _, art, _ = h.run(_billing_full_record())
    res = h.execute(art, ExecutionRequest.faithful_from(art, agent_id="agent-evil"))
    assert res.denial_code == MismatchCode.AGENT_MISMATCH.value


def test_09_expired_authorization_rejected():
    h = _harness()
    _, art, _ = h.run(_billing_full_record(), ttl_seconds=100.0)
    h._clock.advance(101.0)
    res = h.execute(art, ExecutionRequest.faithful_from(art))
    assert res.denial_code == MismatchCode.EXPIRED.value


def test_10_one_time_nonce_cannot_be_replayed():
    h = _harness()
    _, art, res1 = h.run(_billing_full_record(), one_time=True)
    assert res1.executed
    res2 = h.execute(art, ExecutionRequest.faithful_from(art))
    assert res2.denial_code == MismatchCode.REPLAY.value


def test_11_require_approval_not_executable_and_incomplete_rejected():
    h = _harness()
    # (a) A REQUIRE_APPROVAL decision yields no executable authorization.
    dec, art, res = h.run(_billing_full_record(
        actor_role=Role.EXTERNAL_PARTNER, operation=Operation.DISCLOSE,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.UNAPPROVED_EXTERNAL))
    assert art is None and res is None
    # (b) An artifact requiring an incomplete approval is rejected at execution.
    dec2 = h.authorize(_billing_full_record())
    art2 = h.issue(dec2, _billing_full_record(),
                   approval_required=True, approval_completed=False)
    res2 = h.execute(art2, ExecutionRequest.faithful_from(art2))
    assert res2.denial_code == MismatchCode.APPROVAL_INCOMPLETE.value


def test_12_consent_withdrawal_invalidates_execution():
    h = _harness()
    req = _billing_full_record(
        actor_role=Role.EXTERNAL_PARTNER, operation=Operation.DISCLOSE,
        purpose=Purpose.TREATMENT, requested_categories=(DC.DEMOGRAPHIC,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.APPROVED_EXTERNAL,
        destination_approved=True, destination_ref="partner-sys-1",
        consent_state=ConsentState.PRESENT, **{})
    dec, art, _ = h.run(req)
    assert art is not None
    res = h.execute(art, ExecutionRequest.faithful_from(art, consent_state="withdrawn"))
    assert res.denial_code == MismatchCode.CONSENT_CHANGED.value


def test_13_policy_change_invalidates_stale_authorization_when_fresh_required():
    h = _harness()
    _, art, _ = h.run(_billing_full_record(), require_policy_freshness=True)
    res = h.execute(art, ExecutionRequest.faithful_from(art, policy_version="stale-9.9"))
    assert res.denial_code == MismatchCode.POLICY_STALE.value


def test_14_export_mislabeled_as_summary_not_executable():
    # A "summary" to an external unapproved destination in bulk is really an
    # export/exfiltration → decision escalates → no executable authorization.
    h = _harness()
    dec, art, res = h.run(_summarizer_read(
        operation=Operation.SUMMARIZE, recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.UNAPPROVED_EXTERNAL,
        requested_categories=(DC.DIAGNOSIS,), bulk=True, record_count=500))
    assert art is None  # cannot obtain an executable "summary" authorization
    # And even a legitimate SUMMARIZE artifact cannot be used to EXPORT.
    _, art2, _ = h.run(_summarizer_read())
    res2 = h.execute(art2, ExecutionRequest.faithful_from(art2, operation="EXPORT"))
    assert res2.denial_code == MismatchCode.OPERATION_MISMATCH.value


def test_15_cumulative_small_reads_trigger_session_limit():
    h = _harness(session_record_cap=2)
    _, art, r1 = h.run(_billing_full_record(
        requested_categories=(DC.BILLING,)), session_id="s1")
    assert r1.executed
    r2 = h.execute(art, ExecutionRequest.faithful_from(art, session_id="s1"))
    assert r2.executed
    r3 = h.execute(art, ExecutionRequest.faithful_from(art, session_id="s1"))
    assert r3.denial_code == MismatchCode.CUMULATIVE_LIMIT.value


def test_16_restricted_not_recoverable_via_summary_output():
    h = _harness()
    _, art, res = h.run(_summarizer_read())
    assert res.executed
    # The summary output contains no restricted narrative, even though the EMR
    # record holds one.
    assert not any(k in RESTRICTED_VALUES for k in res.payload)
    assert not any(v in json.dumps(res.payload) for v in ("SYN-PSYCH", "SYN-HIV",
                                                          "SYN-REPRO", "SYN-GENOMIC"))


def test_17_prompt_injection_in_clinical_text_cannot_alter_enforcement():
    h = _harness()
    _, art, res = h.run(_summarizer_read())
    # The clinical note (which we DID fetch) carries an injection payload...
    assert SYNTHETIC_INJECTION in res.payload[DC.CLINICAL_NOTE.value]
    # ...but enforcement is deterministic: no restricted/credential leaked.
    assert not any(k in RESTRICTED_VALUES for k in res.payload)
    assert SYNTHETIC_CREDENTIAL_SENTINEL not in json.dumps(res.payload)
    assert DC.AUTH_CREDENTIAL.value not in res.payload


def test_18_caller_non_critical_facts_cannot_downgrade():
    downgrade = {"hc_non_critical": True, "routine_workflow": True,
                 "summary_only": True, "low_risk": True}
    # export
    assert derive_criticality(_billing_full_record(
        actor_role=Role.HOSPITAL_ADMIN, operation=Operation.EXPORT,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        destination_class=DestinationClass.INTERNAL,
        declared_facts=downgrade)).signal == "critical"
    # restricted
    assert derive_criticality(_billing_full_record(
        actor_role=Role.NURSE, operation=Operation.READ, purpose=Purpose.TREATMENT,
        requested_categories=(DC.PSYCH_BEHAVIORAL,), identity_verified=True,
        declared_facts=downgrade)).signal == "critical"
    # cross-tenant
    assert derive_criticality(_billing_full_record(
        actor_role=Role.HOSPITAL_ADMIN, operation=Operation.READ,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        cross_tenant=True, patient_tenant_id="hosp-B", destination_approved=True,
        declared_facts=downgrade)).signal == "critical"
    # external disclosure
    assert derive_criticality(_billing_full_record(
        actor_role=Role.EXTERNAL_PARTNER, operation=Operation.DISCLOSE,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        declared_facts=downgrade)).signal == "critical"


def test_19_critical_promoting_overrides_non_critical_facts():
    d = derive_criticality(_billing_full_record(
        actor_role=Role.HOSPITAL_ADMIN, operation=Operation.EXPORT,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        destination_class=DestinationClass.INTERNAL,
        declared_facts={"hc_non_critical": True, "high_risk": True}))
    assert d.signal == "critical"
    # Reserved control key never survives into facts.
    assert "hc_non_critical" not in d.facts


def test_20_missing_material_facts_fail_conservatively():
    h = _harness()
    # missing purpose on sensitive
    d1, a1, _ = h.run(_summarizer_read(
        actor_role=Role.NURSE, purpose=Purpose.UNSPECIFIED, operation=Operation.READ,
        requested_categories=(DC.PSYCH_BEHAVIORAL,)))
    assert a1 is None
    # missing actor identity → hard block deny
    d2 = h.authorize(_billing_full_record(actor_id="", actor_role=Role.NURSE,
                                          requested_categories=(DC.DIAGNOSIS,)))
    assert d2.outcome.value == "DENY" and d2.hard_block
    # missing destination on export
    d3, a3, _ = h.run(_billing_full_record(
        actor_role=Role.HOSPITAL_ADMIN, operation=Operation.EXPORT,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        destination_class=DestinationClass.UNKNOWN))
    assert a3 is None


# =============================================================================
# Generic-registry invariant tests: non_critical_facts is not a downgrade path
# =============================================================================


def _ctx(facts):
    return RequestContext(
        action_type="X", tool_name="t", risk_level="write", actor_id="a",
        agency_level="FULL", capabilities=(), facts=facts, target_haystack="")


def test_registry_non_critical_fact_alone_is_non_critical():
    reg = build_healthcare_criticality_registry()
    crit, _ = reg.classify(_ctx({"hc_non_critical": True}))
    assert crit == CriticalityClass.NON_CRITICAL


def test_registry_promotion_wins_over_non_critical_fact():
    reg = build_healthcare_criticality_registry()
    crit, _ = reg.classify(_ctx({"hc_critical": True, "hc_non_critical": True}))
    assert crit == CriticalityClass.CRITICAL


def test_registry_declared_promotion_wins():
    reg = build_healthcare_criticality_registry()
    crit, _ = reg.classify(_ctx({"declared_high_risk": True, "hc_non_critical": True}))
    assert crit == CriticalityClass.CRITICAL


def test_registry_unknown_not_downgraded_without_non_critical_signal():
    reg = build_healthcare_criticality_registry()
    # No hc_critical and no hc_non_critical → UNKNOWN (conservative), not
    # non-critical merely because some other fact is present.
    crit, _ = reg.classify(_ctx({"routine_workflow": True}))
    assert crit == CriticalityClass.UNKNOWN


def test_hard_block_overrides_all_non_critical(_hb_harness=None):
    h = _harness()
    d = h.authorize(_billing_full_record(
        actor_role=Role.MEDICAL_RECORDS_STAFF, operation=Operation.READ,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.AUTH_CREDENTIAL,),
        identity_verified=True, declared_facts={"hc_non_critical": True}))
    assert d.outcome.value == "DENY" and d.hard_block


def test_healthcare_unknown_with_non_critical_declared_stays_unknown():
    # An unclassified request (marketing purpose, no critical signal) is UNKNOWN
    # and a caller-declared non-critical fact cannot downgrade it to non-critical.
    d = derive_criticality(_summarizer_read(
        actor_role=Role.HOSPITAL_ADMIN, purpose=Purpose.MARKETING,
        operation=Operation.READ, requested_categories=(DC.DIAGNOSIS,),
        declared_facts={"hc_non_critical": True}))
    assert d.signal == "unknown"
    assert "hc_non_critical" not in d.facts
    # A restricted request with a missing purpose stays at least critical/review
    # (never non-critical) — also not downgradable by the caller.
    d2 = derive_criticality(_summarizer_read(
        actor_role=Role.NURSE, purpose=Purpose.UNSPECIFIED, operation=Operation.READ,
        requested_categories=(DC.PSYCH_BEHAVIORAL,),
        declared_facts={"hc_non_critical": True}))
    assert d2.signal != "non_critical"
    assert "hc_non_critical" not in d2.facts


# =============================================================================
# Metrics + PHI-safety
# =============================================================================


def test_metrics_zero_leakage_and_full_correlation():
    h = _harness()
    # Mix of executed, constrained, and rejected flows.
    _, art, _ = h.run(_billing_full_record())
    h.execute(art, ExecutionRequest.faithful_from(art, patient_ref="patient-002"))
    h.execute(art, ExecutionRequest.faithful_from(art, tenant_id="hosp-B"))
    h.run(_billing_full_record(
        actor_role=Role.EXTERNAL_PARTNER, operation=Operation.DISCLOSE,
        purpose=Purpose.OPERATIONS, requested_categories=(DC.DIAGNOSIS,),
        recipient_type=RecipientType.EXTERNAL_PARTNER,
        destination_class=DestinationClass.UNAPPROVED_EXTERNAL))
    m = h.metrics.to_dict()
    assert m["restricted_field_leakage_count"] == 0
    assert m["unauthorized_field_leakage_count"] == 0
    assert m["tenant_isolation_violations_blocked"] >= 1
    assert m["audit_correlation_completeness"] == 1.0
    assert m["authorizations_denied"] >= 1


def test_receipt_and_artifact_are_phi_free():
    h = _harness()
    _, art, res = h.run(_billing_full_record())
    receipt_blob = json.dumps(res.receipt.to_dict())
    artifact_blob = json.dumps(art.safe_dict())
    # No synthetic raw values leak into governance-facing structures.
    assert "SYN-" not in receipt_blob
    assert "SYN-" not in artifact_blob
    assert SYNTHETIC_CREDENTIAL_SENTINEL not in receipt_blob
    # Raw values live ONLY in the separate payload (delivered, not logged).
    assert "SYN-" in json.dumps(res.payload)
