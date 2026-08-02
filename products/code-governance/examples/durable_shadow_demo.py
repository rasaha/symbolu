"""Deterministic offline MVP 1C demonstration: durable shadow audit persistence.

Shows durable persistence, restart-safe recovery, integrity-verified
reconstruction, tamper detection, staleness, and an offline-verifiable audit
bundle — all with execution DISABLED. No external calls, no execution, no
reservation, no GitHub write path, no external database. The only backend is a
local, append-only, hash-linked stdlib-sqlite3 store.

Run:

    PYTHONPATH=products/code-governance/src:packages/capabilities/action-clearance/src:... \
        python products/code-governance/examples/durable_shadow_demo.py
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

from ugence_code_governance import (
    AuthorizedActor, ClaimInput, ClaimStatus, ClaimType, CodeGovernanceClearanceProfile,
    CodeGovernanceOperationalSnapshot, CodeGovernanceService, DecisionInput, EvidenceRecord,
    InterventionRoutingPolicy, MergeMethod, PersistenceMode, RecoveryStatus,
    RepositoryClassification, RiskTier, SignalSourceEntry, TrustedSignalSourceProjection,
    ValidatorTrustLevel,
)
from ugence_code_governance.persistence import (
    DurableReconstructionState, open_durable_store, reconstruct_from_store,
)
from ugence_code_governance.workflow.records import revision_id_for, workflow_id_for
from ugence_action_clearance import ClearanceStatus, SignalTrustLevel, SignalType

T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
EVAL = T0 + timedelta(minutes=10)
TENANT = "tenant-acme"
LOW = (ClaimType.BUILD, ClaimType.UNIT_TEST, ClaimType.STATIC_ANALYSIS)
REQUIRED = (SignalType.AUTHORIZATION_VALIDITY, SignalType.ACTOR_STATUS, SignalType.ARTIFACT_IDENTITY)
ACTOR = AuthorizedActor(actor_id="user:sre", authority_id="role:merge-approver",
                        decision_scope="merge_pull_request")


def _payload(head):
    return {"action": "opened", "repository": {"name": "billing", "owner": {"login": "acme"}},
            "pull_request": {"number": 77, "base": {"ref": "main", "sha": "base-0"},
                             "head": {"ref": "feat", "sha": head}}, "installation": {"id": "i"}}


def _ev(c, ct):
    return EvidenceRecord.create(tenant_id=c.tenant_id, repository=c.repository,
        pull_request_number=c.pull_request_number, base_sha=c.base_sha, head_sha=c.head_sha,
        evidence_type=ct.value, source_id=ct.value, source_kind="ci", validator_id="ci",
        validator_version="1.0", captured_at=T0, normalized_payload={"r": "pass", "t": ct.value},
        validator_trust_level=ValidatorTrustLevel.TRUSTED)


def _proj():
    return TrustedSignalSourceProjection(projection_id="proj", projection_version="v1", tenant_id=TENANT,
        entries={st: SignalSourceEntry(source_id=f"s-{st.value}", source_kind="approved", adapter_id="ad",
            adapter_version="1.0.0", ingestion_boundary="b", provenance_ref="p",
            max_trust_level=SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE,
            approved_adapter_versions=("1.0.0",)) for st in SignalType})


def _profile():
    return CodeGovernanceClearanceProfile(profile_id="prof", profile_version="v1", tenant_id=TENANT,
        repository_classification=RepositoryClassification.MEDIUM, required_signal_types=REQUIRED,
        trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,),
        minimum_trust_levels={SignalType.ARTIFACT_IDENTITY: SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION},
        maximum_shadow_clearance_lifetime_s=3600, incident_response=ClearanceStatus.HOLD)


def _snap(action):
    return CodeGovernanceOperationalSnapshot(captured_at=T0, valid_until=T0 + timedelta(hours=2),
        authorization_validity="VALID", actor_state="ACTIVE",
        artifact_action_fingerprint=action.fingerprint, artifact_target_ref=action.repository)


def _rid(c):
    return revision_id_for(workflow_id_for(TENANT, c.repository, 77), c.base_sha, c.head_sha)


def _drive_full(svc, head):
    c = svc.ingest_change_event(_payload(head), tenant_id=TENANT, captured_at=T0, delivery_id=head)
    rid = _rid(c)
    for ct in LOW:
        svc.record_evidence(TENANT, rid, _ev(c, ct))
    svc.build_claim_manifest(TENANT, rid, risk_tier=RiskTier.LOW,
        claim_inputs=tuple(ClaimInput(claim_type=ct, status=ClaimStatus.SATISFIED, evidence=(_ev(c, ct),)) for ct in LOW),
        captured_at=T0)
    svc.evaluate_claim_requirements(TENANT, rid, at=T0)
    svc.evaluate_assertions(TENANT, rid, at=T0)
    svc.create_recommendation(TENANT, rid, created_at=T0)
    svc.record_authorized_decision(TENANT, rid, actor=ACTOR, decision=DecisionInput(outcome="APPROVE"), at=T0)
    action = svc.prepare_exact_action(TENANT, rid, merge_method=MergeMethod.SQUASH, at=T0)
    svc.evaluate_action_shadow(TENANT, rid, at=T0, finalize=False)
    svc.record_operational_snapshot(TENANT, rid, _snap(action), projection=_proj(), profile=_profile(), at=EVAL)
    svc.evaluate_action_clearance_shadow(TENANT, rid, evaluation_time=EVAL)
    svc.assess_human_intervention(TENANT, rid, at=EVAL, routing=InterventionRoutingPolicy())
    return c, rid, action


def run(verbose=True):
    out = {}
    path = os.path.join(tempfile.mkdtemp(prefix="cg-durable-demo-"), "governance.db")

    def say(msg):
        if verbose:
            print(msg)

    say("== Code Governance MVP 1C — durable shadow audit persistence demonstration ==")

    # 1. Durable run persisted to a local append-only, hash-linked SQLite store.
    svc = CodeGovernanceService(store_path=path)
    c, rid, action = _drive_full(svc, "head-AAA")
    wid = svc.get_workflow(TENANT, rid).workflow_id
    hc = svc.durable_store.health_check()
    say(f"  [1 persist ] state=SHADOW_COMPLETE records={hc['record_count']} "
        f"events={hc['event_count']} classification={hc['classification']}")
    out["records"] = hc["record_count"]
    out["events"] = hc["event_count"]
    out["exec"] = svc.execution_status()
    svc.close()  # close == process shutdown

    # 2. Restart: a brand-new service reopens the store and recovers the workflow.
    svc2 = CodeGovernanceService(store_path=path)
    rec = svc2.resume_workflow(TENANT, rid)
    say(f"  [2 restart ] recovery={rec.status.value} last_state={rec.last_committed_state} "
        f"exec={rec.execution_status} requires_action={rec.requires_explicit_action}")
    out["recovery"] = rec.status.value

    # 3. Integrity-verified reconstruction entirely from persisted projections.
    result = svc2.reconstruct_chain_from_store(TENANT, rid)
    say(f"  [3 reconst ] state={result.state.value} verified_links={len(result.verified_links)} "
        f"exec={result.execution_status}")
    out["reconstruction"] = result.state.value

    # 4. Offline-verifiable audit bundle (no store connection needed to verify).
    bundle = svc2.export_governance_audit_bundle(TENANT, rid)
    verification = CodeGovernanceService.verify_governance_audit_bundle(bundle)
    say(f"  [4 bundle  ] fingerprint={bundle['bundle_fingerprint'][:16]}… "
        f"offline_verify_ok={verification.ok} exec={bundle['execution_status']}")
    out["bundle_ok"] = verification.ok
    out["bundle_fingerprint"] = bundle["bundle_fingerprint"]

    # 5. Staleness: a newer head supersedes the reconstructed chain (no network).
    stale = svc2.reconstruct_chain_from_store(TENANT, rid, current_head_sha="head-BBB")
    say(f"  [5 stale   ] reconstruction against newer head={stale.state.value}")
    out["stale"] = stale.state.value
    svc2.close()

    # 6. Tamper evidence: raw mutation is caught by fingerprint recomputation.
    conn = sqlite3.connect(path)
    conn.execute("DROP TRIGGER records_no_update")
    conn.execute("UPDATE records SET canonical_payload='{\"tampered\":true}' "
                 "WHERE record_type='CLAIM_MANIFEST'")
    conn.commit()
    conn.close()
    store = open_durable_store(path)
    tampered = reconstruct_from_store(store, TENANT, rid)
    say(f"  [6 tamper  ] reconstruction after raw mutation={tampered.state.value}")
    out["tamper"] = tampered.state.value
    store.close()

    # 7. Boundaries.
    say("  [7 bounds  ] no execution · no reservation · no execution-consumption ledger · "
        "no external DB · no GitHub write path")
    say("== demonstration complete — execution remains DISABLED ==")
    out["persistence"] = "DURABLE_SHADOW_REFERENCE"
    out["reservation"] = "NONE"
    return out


if __name__ == "__main__":
    run()
