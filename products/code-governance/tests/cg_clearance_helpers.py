"""Shared builders for MVP 1B (Action Clearance shadow integration) tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cg_helpers import (
    LOW_CLAIMS, T0, claim_inputs_for, make_evidence, make_payload, revision_of,
)
from ugence_code_governance import (
    AuthorizedActor, CodeGovernanceClearanceProfile, CodeGovernanceOperationalSnapshot,
    CodeGovernanceService, DecisionInput, InterventionRoutingPolicy, MergeMethod,
    RepositoryClassification, RiskTier, SignalSourceEntry, TrustedSignalSourceProjection,
)
from ugence_action_clearance import ClearanceStatus, SignalTrustLevel, SignalType

EVAL = T0 + timedelta(minutes=10)
ALL_SIGNAL_TYPES = tuple(SignalType)
REQUIRED = (SignalType.AUTHORIZATION_VALIDITY, SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY)
ACTOR = AuthorizedActor(actor_id="user:approver", authority_id="role:code-approver",
                        decision_scope="merge_pull_request")


def source_entry(signal_type, *, max_trust=SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE,
                 adapter_version="1.0.0", approved_versions=("1.0.0",)):
    return SignalSourceEntry(
        source_id=f"src-{signal_type.value}", source_kind="approved-source",
        adapter_id="cg-adapter", adapter_version=adapter_version, ingestion_boundary="cg-boundary",
        provenance_ref=f"prov-{signal_type.value}", max_trust_level=max_trust,
        approved_adapter_versions=approved_versions)


def projection(signal_types=ALL_SIGNAL_TYPES, *, tenant="acme", **kw):
    return TrustedSignalSourceProjection(
        projection_id="cg-projection", projection_version="v1", tenant_id=tenant,
        entries={st: source_entry(st, **kw) for st in signal_types})


def profile(*, classification=RepositoryClassification.MEDIUM, incident_escalate=False,
            required=REQUIRED, trust_required=(SignalType.ARTIFACT_IDENTITY,),
            min_trust=None, automatic=True, sensitive_components=(), max_lifetime_s=3600):
    return CodeGovernanceClearanceProfile(
        profile_id="cg-clearance", profile_version="v1", tenant_id="acme",
        repository_classification=classification, required_signal_types=required,
        trust_required_signal_types=trust_required,
        minimum_trust_levels=(min_trust or {SignalType.ARTIFACT_IDENTITY: SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION}),
        maximum_shadow_clearance_lifetime_s=max_lifetime_s,
        incident_response=ClearanceStatus.ESCALATE if incident_escalate else ClearanceStatus.HOLD,
        automatic_continuation_eligible=automatic, sensitive_components=sensitive_components)


def snapshot(action, *, captured_at=T0, valid_hours=2, **overrides):
    base = dict(authorization_validity="VALID", actor_state="ACTIVE",
                artifact_action_fingerprint=action.fingerprint, artifact_target_ref=action.repository)
    base.update(overrides)
    return CodeGovernanceOperationalSnapshot(
        captured_at=captured_at, valid_until=captured_at + timedelta(hours=valid_hours), **base)


def drive_to_action_evaluated(svc, *, head_sha="head-sha-1", merge_method=MergeMethod.SQUASH,
                              actiongate=None):
    """Run MVP 1A up to ACTION_EVALUATED (finalize=False) and return refs."""
    if actiongate is not None:
        svc._actiongate = actiongate
    change = svc.ingest_change_event(make_payload(head_sha=head_sha), tenant_id="acme",
                                     captured_at=T0, delivery_id=head_sha)
    rid = revision_of(change)
    for ct in LOW_CLAIMS:
        svc.record_evidence("acme", rid, make_evidence(change, ct))
    svc.build_claim_manifest("acme", rid, risk_tier=RiskTier.LOW,
                             claim_inputs=claim_inputs_for(change, LOW_CLAIMS), captured_at=T0)
    svc.evaluate_claim_requirements("acme", rid, at=T0)
    svc.evaluate_assertions("acme", rid, at=T0)
    svc.create_recommendation("acme", rid, created_at=T0)
    svc.record_authorized_decision("acme", rid, actor=ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    action = svc.prepare_exact_action("acme", rid, merge_method=merge_method, at=T0)
    shadow = svc.evaluate_action_shadow("acme", rid, at=T0, finalize=False)
    return change, rid, action, shadow


def run_clearance(svc, rid, action, *, snap=None, proj=None, prof=None, routing=None,
                  sensitive=False, evaluation_time=EVAL):
    snap = snap if snap is not None else snapshot(action)
    proj = proj if proj is not None else projection()
    prof = prof if prof is not None else profile()
    svc.record_operational_snapshot("acme", rid, snap, projection=proj, profile=prof, at=evaluation_time)
    record = svc.evaluate_action_clearance_shadow("acme", rid, evaluation_time=evaluation_time)
    assessment = svc.assess_human_intervention("acme", rid, at=evaluation_time,
                                               routing=routing or InterventionRoutingPolicy(),
                                               sensitive=sensitive)
    return record, assessment


def full_1b(*, snap_overrides=None, classification=RepositoryClassification.MEDIUM,
            incident_escalate=False, sensitive=False, actiongate=None, head_sha="head-sha-1",
            automatic=True):
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc, head_sha=head_sha, actiongate=actiongate)
    prof = profile(classification=classification, incident_escalate=incident_escalate, automatic=automatic)
    record, assessment = run_clearance(svc, rid, action, snap=snapshot(action, **(snap_overrides or {})),
                                       prof=prof, sensitive=sensitive)
    result = svc.reconstruct_chain("acme", rid)
    return svc, rid, action, shadow, record, assessment, result
