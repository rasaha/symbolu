"""Durable workflow journal — maps each shadow workflow stage to one atomic,
append-only durable commit.

The journal is the *only* thing the service talks to when durable mode is on. It
builds minimal, data-minimized **audit projections** (reference + fingerprint +
governance-relevant linkage) for each stage — never re-issued authority records —
and commits them together with one hash-linked workflow event. A stage never
becomes visible as committed unless every record for that stage persisted.

Payloads are intentionally minimal: no diffs, no tokens, no secrets, no unrelated
PII. Externally-owned records (DecisionRecord, CER, ActionGate result, TAP result)
appear only as projections carrying their identity + content hash.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .recorder import (
    DurableShadowRecorder,
    rid_actiongate_projection,
    rid_cer_projection,
    rid_change_identity,
    rid_clearance_request,
    rid_decision_projection,
    rid_operational_snapshot,
    rid_prepared_action,
    rid_tap_projection,
    rid_workflow_revision,
)
from .schema import RecordType, WorkflowEventType
from .sqlite import DurableShadowStore

_Spec = Tuple[RecordType, str, object]


class DurableWorkflowJournal:
    """Stage-oriented facade over :class:`DurableShadowRecorder`."""

    def __init__(self, store: DurableShadowStore) -> None:
        self._store = store
        self._recorder = DurableShadowRecorder(store)

    @property
    def store(self) -> DurableShadowStore:
        return self._store

    # --- internal commit -------------------------------------------------
    def _from_state(self, tenant_id: str, revision_id: str) -> str:
        index = self._store.get_index(tenant_id, revision_id)
        return index["current_state"] if index else "INIT"

    def _commit(
        self,
        run,
        tenant_id: str,
        at: datetime,
        specs: List[_Spec],
        *,
        event_id: Optional[str] = None,
        event_type: WorkflowEventType = WorkflowEventType.STAGE_COMMITTED,
        chain_id: Optional[str] = None,
    ) -> str:
        return self._recorder.commit_stage(
            tenant_id=tenant_id, workflow_id=run.workflow_id, revision_id=run.revision_id,
            occurred_at=at, from_state=self._from_state(tenant_id, run.revision_id),
            to_state=run.state.value, record_specs=specs, event_type=event_type,
            chain_id=chain_id, event_id=event_id)

    # --- stages ----------------------------------------------------------
    def on_change_identity(self, run, tenant_id: str, at: datetime) -> None:
        change = run.change
        payload = {
            "change_fingerprint": change.fingerprint,
            "repository": change.repository,
            "pull_request_number": change.pull_request_number,
            "base_sha": change.base_sha,
            "head_sha": change.head_sha,
            "target_branch": change.target_branch,
        }
        rid = rid_change_identity(change.fingerprint)
        self._commit(run, tenant_id, at,
                     [(RecordType.GOVERNED_CHANGE_IDENTITY, rid, payload)],
                     event_id=f"{run.revision_id}:identity")

    def on_evidence(self, run, tenant_id: str, evidence, at: datetime) -> None:
        eid = evidence.evidence_id
        payload = {
            "evidence_id": eid,
            "evidence_fingerprint": getattr(evidence, "fingerprint", None),
            "claim_type": getattr(getattr(evidence, "claim_type", None), "value",
                                  getattr(evidence, "claim_type", None)),
            "head_sha": getattr(evidence, "head_sha", None),
        }
        self._commit(run, tenant_id, at,
                     [(RecordType.EVIDENCE_RECORD, eid, payload)],
                     event_id=f"{run.revision_id}:evidence:{eid}")

    def on_claim_manifest(self, run, tenant_id: str, manifest, risk_tier, at: datetime) -> None:
        payload = {
            "manifest_id": manifest.manifest_id,
            "manifest_fingerprint": manifest.fingerprint,
            "policy_ref": manifest.policy_ref,
            "risk_tier": getattr(risk_tier, "value", risk_tier),
        }
        self._commit(run, tenant_id, at,
                     [(RecordType.CLAIM_MANIFEST, manifest.manifest_id, payload)],
                     event_id=f"{run.revision_id}:claim_manifest")

    def on_claim_evaluation(self, run, tenant_id: str, evaluation, at: datetime,
                            *, failed_closed: bool = False) -> None:
        payload = {
            "proceed": bool(evaluation.proceed),
            "missing_required_claims": list(getattr(evaluation, "missing_required_claims", ()) or ()),
            "incomplete_required_claims": list(
                getattr(evaluation, "incomplete_required_claims", ()) or ()),
        }
        rid = f"claimeval:{run.revision_id}"
        self._commit(run, tenant_id, at,
                     [(RecordType.CLAIM_EVALUATION, rid, payload)],
                     event_id=f"{run.revision_id}:claim_evaluation",
                     event_type=(WorkflowEventType.STAGE_FAILED_CLOSED if failed_closed
                                 else WorkflowEventType.STAGE_COMMITTED))

    def on_assertions(self, run, tenant_id: str, tap_eval, at: datetime) -> None:
        payload = {
            "manifest_fingerprint": run.claim_manifest_fingerprint or "",
            "request_fingerprints": list(run.tap_request_fingerprints),
            "result_fingerprints": list(run.tap_result_fingerprints),
        }
        rid = rid_tap_projection(run.claim_manifest_fingerprint or run.revision_id)
        self._commit(run, tenant_id, at,
                     [(RecordType.TAP_RESULT_PROJECTION, rid, payload)],
                     event_id=f"{run.revision_id}:assertions")

    def on_recommendation(self, run, tenant_id: str, rec, at: datetime) -> None:
        payload = {
            "recommendation_id": rec.recommendation_id,
            "recommendation_fingerprint": rec.fingerprint,
            "disposition": getattr(rec.disposition, "value", rec.disposition),
        }
        self._commit(run, tenant_id, at,
                     [(RecordType.GOVERNANCE_RECOMMENDATION, rec.recommendation_id, payload)],
                     event_id=f"{run.revision_id}:recommendation")

    def on_decision(self, run, tenant_id: str, decision_record, at: datetime,
                    *, failed_closed: bool = False) -> None:
        did = decision_record.decision_id
        payload = {
            "decision_record_id": did,
            "decision_outcome": getattr(
                getattr(decision_record, "outcome", None), "value",
                getattr(decision_record, "outcome", None)),
            "decision_fingerprint": getattr(decision_record, "fingerprint", None),
        }
        self._commit(run, tenant_id, at,
                     [(RecordType.DECISION_RECORD_PROJECTION,
                       rid_decision_projection(did), payload)],
                     event_id=f"{run.revision_id}:decision",
                     event_type=(WorkflowEventType.STAGE_FAILED_CLOSED if failed_closed
                                 else WorkflowEventType.STAGE_COMMITTED))

    def on_fail_closed(self, run, tenant_id: str, at: datetime) -> None:
        """Record a fail-closed terminal transition that produced no new record."""
        self._commit(run, tenant_id, at, [],
                     event_id=f"{run.revision_id}:failclosed:{run.state.value}",
                     event_type=WorkflowEventType.STAGE_FAILED_CLOSED)

    def on_prepared_action(self, run, tenant_id: str, cer, action, at: datetime) -> None:
        cer_payload = {"cer_id": cer.cer_id, "cer_content_hash": cer.content_hash}
        action_payload = {
            "prepared_action_fingerprint": action.fingerprint,
            "repository": action.repository,
            "pull_request_number": action.pull_request_number,
            "base_sha": action.base_sha,
            "head_sha": action.head_sha,
            "merge_method": getattr(action.merge_method, "value", action.merge_method),
            "decision_record_id": action.decision_record_id,
            "cer_id": action.cer_id,
        }
        self._commit(run, tenant_id, at, [
            (RecordType.CONTEXT_ENVELOPE_PROJECTION, rid_cer_projection(cer.cer_id), cer_payload),
            (RecordType.PREPARED_MERGE_ACTION, rid_prepared_action(action.fingerprint),
             action_payload),
        ], event_id=f"{run.revision_id}:prepared_action")

    def on_action_shadow(self, run, tenant_id: str, evaluation, at: datetime) -> None:
        payload = {
            "action_request_fingerprint": evaluation.request_fingerprint,
            "action_result_fingerprint": evaluation.result_fingerprint,
            "outcome": getattr(evaluation.outcome, "value", evaluation.outcome),
        }
        rid = rid_actiongate_projection(evaluation.result_fingerprint)
        self._commit(run, tenant_id, at,
                     [(RecordType.ACTIONGATE_RESULT_PROJECTION, rid, payload)],
                     event_id=f"{run.revision_id}:action_shadow")

    def on_operational_snapshot(self, run, tenant_id: str, snapshot, at: datetime) -> None:
        fp = getattr(snapshot, "fingerprint", None) or run.revision_id
        payload = {
            "snapshot_fingerprint": getattr(snapshot, "fingerprint", None),
            "captured_at": getattr(snapshot, "captured_at", None),
        }
        rid = rid_operational_snapshot(run.revision_id, fp)
        self._commit(run, tenant_id, at,
                     [(RecordType.OPERATIONAL_SNAPSHOT, rid, payload)],
                     event_id=f"{run.revision_id}:operational_snapshot")

    def on_clearance_evaluation(self, run, tenant_id: str, record, at: datetime,
                                *, failed_closed: bool = False) -> None:
        payload = {
            "record_id": record.record_id,
            "stage_state": getattr(record.stage_state, "value", record.stage_state),
            "clearance_status": record.clearance_status or "",
            "clearance_request_fingerprint": record.clearance_request_fingerprint or "",
            "clearance_result_fingerprint": record.clearance_result_fingerprint or "",
            "action_result_fingerprint": record.action_result_fingerprint or "",
            "reason_codes": list(record.reason_codes),
        }
        specs: List[_Spec] = [
            (RecordType.ACTION_CLEARANCE_EVALUATION, record.record_id, payload)]
        # An evaluated clearance also persists the neutral clearance-request projection.
        if record.clearance_request_fingerprint:
            specs.append((
                RecordType.CLEARANCE_REQUEST_PROJECTION,
                rid_clearance_request(record.clearance_request_fingerprint),
                {"clearance_request_fingerprint": record.clearance_request_fingerprint,
                 "signal_bundle_fingerprint": record.signal_bundle_fingerprint or ""}))
        self._commit(run, tenant_id, at, specs,
                     event_id=f"{run.revision_id}:clearance_evaluation",
                     event_type=(WorkflowEventType.STAGE_FAILED_CLOSED if failed_closed
                                 else WorkflowEventType.STAGE_COMMITTED))

    def on_intervention(self, run, tenant_id: str, assessment, at: datetime) -> None:
        payload = {
            "assessment_id": assessment.assessment_id,
            "assessment_fingerprint": getattr(assessment, "fingerprint", None),
            "required": bool(assessment.required),
            "required_authorities": list(getattr(assessment, "required_authorities", ()) or ()),
        }
        self._commit(run, tenant_id, at,
                     [(RecordType.HUMAN_INTERVENTION_ASSESSMENT,
                       assessment.assessment_id, payload)],
                     event_id=f"{run.revision_id}:intervention")

    def on_finalized(self, run, tenant_id: str, chain_id: str, at: datetime,
                     *, chain_payload: Dict[str, Any]) -> None:
        revision_payload = {
            "revision_id": run.revision_id,
            "workflow_id": run.workflow_id,
            "current_state": run.state.value,
            "chain_id": chain_id,
        }
        self._commit(run, tenant_id, at, [
            (RecordType.GOVERNANCE_CHAIN, chain_id, chain_payload),
            (RecordType.WORKFLOW_REVISION, rid_workflow_revision(run.revision_id),
             revision_payload),
        ], event_id=f"{run.revision_id}:finalized", chain_id=chain_id)


__all__ = ["DurableWorkflowJournal"]
