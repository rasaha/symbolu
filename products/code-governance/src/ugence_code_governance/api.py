"""Read-only public product service API for Code Governance (MVP 1A).

``CodeGovernanceService`` is the curated product surface. It coordinates the
shadow governance pipeline and exposes exactly the read-only operations MVP 1A
requires. No operation executes or mutates GitHub. There is deliberately no
``merge()`` or ``execute()`` method; :meth:`execution_status` always returns
``DISABLED``.

Pipeline (each stage fails closed):

```
ingest_change_event -> record_evidence* -> build_claim_manifest
    -> evaluate_claim_requirements -> evaluate_assertions -> create_recommendation
    -> record_authorized_decision -> prepare_exact_action -> evaluate_action_shadow
    -> reconstruct_chain
```
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Tuple

from .claims.builder import ClaimInput, build_claim_manifest
from .claims.manifest import ClaimManifest
from .claims.requirements import ClaimEvaluation, evaluate_claim_requirements
from .errors import (
    DecisionAuthorityRequiredError,
    RecordNotFoundError,
    StaleEvidenceError,
    CrossTenantAccessError,
)
from .evidence.records import EvidenceRecord
from .governance.actiongate_adapter import ActionGateShadowAdapter, ShadowActionEvaluation
from .governance.kernel import AuthorizedActor, DecisionCerKernel, DecisionInput
from .governance.prepared_action import PreparedMergeAction
from .governance.recommendation import GovernanceRecommendation, RecommendationDisposition
from .governance.tap_adapter import TapClaimAdapter, TapEvaluation
from .models.change_identity import GovernedChangeIdentity
from .models.enums import (
    ExecutionStatus,
    MergeMethod,
    RiskTier,
    WorkflowMode,
    WorkflowState,
)
from .persistence.memory import (
    InMemoryClaimManifestRepository,
    InMemoryEvidenceRepository,
    InMemoryGovernanceChainRepository,
    InMemoryPreparedActionRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from .policies.profiles import DEFAULT_POLICY, RepositoryPolicy
from .reconstruction.records import GovernanceChainRecord, chain_id_for
from .reconstruction.service import ChainReconstructionService, ReconstructionResult
from .fingerprints import domain_hash
from .github.normalizer import normalize_pull_request_event
from .workflow.service import WorkflowRun, new_run
from .models.enums import ActionClearanceStatus
from .clearance.adapter import ActionClearanceShadowAdapter, is_eligible
from .clearance.intervention import (
    HumanInterventionAssessment,
    InterventionRoutingPolicy,
    assess_intervention,
)
from .clearance.profile import CodeGovernanceClearanceProfile
from .clearance.records import ActionClearanceEvaluationRecord, evaluation_record_id
from .clearance.signal_adapter import ClearanceInputError, build_trusted_signals
from .clearance.snapshot import CodeGovernanceOperationalSnapshot
from .clearance.source_projection import TrustedSignalSourceProjection

# Canonical Action Clearance evaluator — public API only.
from ugence_action_clearance import evaluate_clearance  # type: ignore
from ugence_action_clearance import ClearanceStatus  # type: ignore


class CodeGovernanceService:
    """The product's read-only shadow governance service."""

    def __init__(self, *, policy: Optional[RepositoryPolicy] = None) -> None:
        self._policy = policy or DEFAULT_POLICY
        self._evidence_repo = InMemoryEvidenceRepository()
        self._claim_repo = InMemoryClaimManifestRepository()
        self._rec_repo = InMemoryRecommendationRepository()
        self._action_repo = InMemoryPreparedActionRepository()
        self._workflow_repo = InMemoryWorkflowRepository()
        self._chain_repo = InMemoryGovernanceChainRepository()
        self._kernel = DecisionCerKernel()
        self._tap = TapClaimAdapter()
        self._actiongate = ActionGateShadowAdapter()
        self._clearance_adapter = ActionClearanceShadowAdapter()
        # shadow/reference in-memory clearance records (tenant-keyed; immutable)
        self._clearance_eval_repo: Dict[Tuple[str, str], ActionClearanceEvaluationRecord] = {}
        self._intervention_repo: Dict[Tuple[str, str], HumanInterventionAssessment] = {}
        self._reconstruction = ChainReconstructionService(
            evidence_repo=self._evidence_repo,
            claim_repo=self._claim_repo,
            recommendation_repo=self._rec_repo,
            prepared_action_repo=self._action_repo,
            workflow_repo=self._workflow_repo,
            chain_repo=self._chain_repo,
            clearance_eval_repo=self._clearance_eval_repo,
            intervention_repo=self._intervention_repo,
        )
        # live run contexts keyed by (tenant_id, revision_id)
        self._runs: Dict[Tuple[str, str], WorkflowRun] = {}
        # lineage currency: workflow_id -> current head sha
        self._current_head: Dict[str, str] = {}
        # per-run scratch (manifest, evaluation, tap eval, decision, cer)
        self._scratch: Dict[Tuple[str, str], Dict[str, Any]] = {}

    # --- helpers ---------------------------------------------------------
    def _run(self, tenant_id: str, revision_id: str) -> WorkflowRun:
        run = self._runs.get((tenant_id, revision_id))
        if run is None:
            raise RecordNotFoundError(f"no workflow run for revision {revision_id}")
        return run

    def _scr(self, tenant_id: str, revision_id: str) -> Dict[str, Any]:
        return self._scratch.setdefault((tenant_id, revision_id), {})

    def _persist_snapshot(self, run: WorkflowRun) -> None:
        self._workflow_repo.put(run.snapshot())

    # --- 1. ingestion + identity ----------------------------------------
    def ingest_change_event(
        self,
        payload: Mapping[str, Any],
        *,
        tenant_id: str,
        captured_at: datetime,
        delivery_id: str,
        event_source: str = "github",
        installation_tenant_map: Optional[Mapping[str, str]] = None,
        secret: Optional[str] = None,
        signature_header: Optional[str] = None,
        raw_body: Optional[bytes] = None,
        merge_method: Optional[MergeMethod] = None,
    ) -> GovernedChangeIdentity:
        """Ingest a supplied/fixture GitHub PR event (read-only) → change identity.

        Idempotent per revision: re-delivery of the same event returns the same
        governed change and does not create a new revision. A changed head SHA
        creates a new revision under the same workflow lineage.
        """
        change = normalize_pull_request_event(
            payload, tenant_id=tenant_id, captured_at=captured_at,
            delivery_id=delivery_id, event_source=event_source,
            installation_tenant_map=installation_tenant_map,
            secret=secret, signature_header=signature_header, raw_body=raw_body,
            merge_method=merge_method,
        )
        run = new_run(change, at=captured_at)
        key = (tenant_id, run.revision_id)
        if key in self._runs:  # idempotent re-delivery
            return self._runs[key].change
        self._runs[key] = run
        self._current_head[run.workflow_id] = change.head_sha
        # The immutable WorkflowRevision snapshot is persisted once, at a terminal
        # state (SHADOW_COMPLETE or a fail-closed terminal). Intermediate reads use
        # the live run via get_workflow().
        return change

    # --- 2. evidence -----------------------------------------------------
    def record_evidence(
        self, tenant_id: str, revision_id: str, record: EvidenceRecord
    ) -> EvidenceRecord:
        """Store an immutable evidence record and admit it if current-head."""
        run = self._run(tenant_id, revision_id)
        if record.tenant_id != tenant_id:
            raise CrossTenantAccessError("evidence tenant does not match workflow tenant")
        self._evidence_repo.put(record)
        if record.is_current_for(run.change.head_sha):
            if run.state is WorkflowState.IDENTITY_BOUND:
                run.transition(WorkflowState.EVIDENCE_PENDING, at=record.captured_at)
            if record.evidence_id not in run.evidence_ids:
                run.evidence_ids.append(record.evidence_id)
        return record

    # --- 3. claim manifest ----------------------------------------------
    def build_claim_manifest(
        self,
        tenant_id: str,
        revision_id: str,
        *,
        risk_tier: RiskTier,
        claim_inputs: Tuple[ClaimInput, ...],
        captured_at: datetime,
    ) -> ClaimManifest:
        run = self._run(tenant_id, revision_id)
        if run.state is WorkflowState.IDENTITY_BOUND:
            run.transition(WorkflowState.EVIDENCE_PENDING, at=captured_at)
        manifest = build_claim_manifest(
            change=run.change, policy=self._policy, risk_tier=risk_tier,
            claim_inputs=claim_inputs, captured_at=captured_at)
        self._claim_repo.put(manifest)
        run.transition(WorkflowState.EVIDENCE_COMPLETE, at=captured_at)
        run.claim_manifest_id = manifest.manifest_id
        run.claim_manifest_fingerprint = manifest.fingerprint
        run.policy_refs = (manifest.policy_ref,)
        self._scr(tenant_id, revision_id)["manifest"] = manifest
        self._scr(tenant_id, revision_id)["risk_tier"] = risk_tier
        return manifest

    # --- 4. non-compensatory claim evaluation ---------------------------
    def evaluate_claim_requirements(
        self, tenant_id: str, revision_id: str, *, at: Optional[datetime] = None
    ) -> ClaimEvaluation:
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        manifest: ClaimManifest = scr["manifest"]
        risk_tier: RiskTier = scr["risk_tier"]
        evaluation = evaluate_claim_requirements(
            manifest, self._policy.requirements_for(risk_tier))
        when = at or run.updated_at
        if not evaluation.proceed:
            # Fail closed — mandatory gate not satisfied.
            run.transition(WorkflowState.CLAIMS_INCOMPLETE, at=when)
            self._persist_snapshot(run)
        else:
            run.transition(WorkflowState.CLAIMS_EVALUATED, at=when)
        scr["evaluation"] = evaluation
        return evaluation

    # --- 5. TAP assertion evaluation ------------------------------------
    def evaluate_assertions(
        self, tenant_id: str, revision_id: str, *, at: Optional[datetime] = None
    ) -> TapEvaluation:
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        manifest: ClaimManifest = scr["manifest"]
        tap_eval = self._tap.evaluate_manifest(manifest)
        run.tap_request_fingerprints = tuple(r.request_fingerprint for r in tap_eval.results)
        run.tap_result_fingerprints = tuple(r.result_fingerprint for r in tap_eval.results)
        run.transition(WorkflowState.ASSERTIONS_EVALUATED, at=at or run.updated_at)
        scr["tap_eval"] = tap_eval
        return tap_eval

    # --- 6. advisory recommendation -------------------------------------
    def create_recommendation(
        self, tenant_id: str, revision_id: str, *, created_at: datetime
    ) -> GovernanceRecommendation:
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        manifest: ClaimManifest = scr["manifest"]
        evaluation: ClaimEvaluation = scr["evaluation"]
        if evaluation.proceed:
            disposition = RecommendationDisposition.RECOMMEND_PROCEED
            rationale = ("all mandatory claims satisfied (advisory)",)
        elif evaluation.missing_required_claims or evaluation.incomplete_required_claims:
            disposition = RecommendationDisposition.INSUFFICIENT_EVIDENCE
            rationale = ("mandatory claims missing/incomplete (advisory)",)
        else:
            disposition = RecommendationDisposition.RECOMMEND_HOLD
            rationale = ("one or more mandatory claims not satisfied (advisory)",)
        rec_id = domain_hash("recommendation_id.v1",
                             {"change": run.change.fingerprint,
                              "manifest": manifest.fingerprint})[:24]
        rec = GovernanceRecommendation(
            recommendation_id=rec_id,
            tenant_id=tenant_id,
            repository=run.change.repository,
            pull_request_number=run.change.pull_request_number,
            change_fingerprint=run.change.fingerprint,
            claim_manifest_fingerprint=manifest.fingerprint,
            disposition=disposition,
            rationale=rationale,
            created_at=created_at,
            policy_ref=manifest.policy_ref,
        )
        self._rec_repo.put(rec)
        run.recommendation_id = rec.recommendation_id
        run.recommendation_fingerprint = rec.fingerprint
        scr["recommendation"] = rec
        return rec

    # --- 7. explicit authorized decision --------------------------------
    def record_authorized_decision(
        self,
        tenant_id: str,
        revision_id: str,
        *,
        actor: Optional[AuthorizedActor],
        decision: DecisionInput,
        at: datetime,
    ):
        """Record a binding DecisionRecord under an explicit authorized actor.

        The Workflow Service never mints the decision. Without an authorized
        actor the workflow enters ``DECISION_REQUIRED`` and fails closed.
        """
        run = self._run(tenant_id, revision_id)
        run.transition(WorkflowState.DECISION_PENDING, at=at)
        if actor is None:
            run.transition(WorkflowState.DECISION_REQUIRED, at=at)
            self._persist_snapshot(run)
            raise DecisionAuthorityRequiredError(
                "a binding decision requires an explicit authorized actor")
        record = self._kernel.record_authorized_decision(
            run.change, actor=actor, decision=decision, policy_refs=())
        outcome = decision.outcome.upper()
        if outcome in ("DENY", "REJECT"):
            run.decision_record_id = record.decision_id
            run.transition(WorkflowState.BLOCKED, at=at)
            self._persist_snapshot(run)
            self._scr(tenant_id, revision_id)["decision"] = record
            self._scr(tenant_id, revision_id)["actor"] = actor
            return record
        run.decision_record_id = record.decision_id
        run.transition(WorkflowState.DECISION_RECORDED, at=at)
        self._scr(tenant_id, revision_id)["decision"] = record
        self._scr(tenant_id, revision_id)["actor"] = actor
        return record

    # --- 8. CER binding + prepared exact action -------------------------
    def prepare_exact_action(
        self,
        tenant_id: str,
        revision_id: str,
        *,
        merge_method: MergeMethod,
        at: datetime,
        expiry: Optional[datetime] = None,
        expected_tree_sha: Optional[str] = None,
    ) -> PreparedMergeAction:
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        decision = scr["decision"]
        actor: AuthorizedActor = scr["actor"]
        change = run.change
        # Bind canonical cer.v1 CER referencing the decision.
        params = {
            "repository": change.repository,
            "pull_request_number": str(change.pull_request_number),
            "base_sha": change.base_sha,
            "head_sha": change.head_sha,
            "merge_method": merge_method.value,
            "target_branch": change.target_branch,
        }
        cer = self._kernel.bind_context_envelope(
            change, decision, actor=actor, requested_parameters=params)
        run.cer_id = cer.cer_id
        run.cer_content_hash = cer.content_hash
        run.transition(WorkflowState.CONTEXT_BOUND, at=at)
        # Build the exact prepared action (not authorization).
        action = PreparedMergeAction(
            tenant_id=tenant_id,
            repository=change.repository,
            pull_request_number=change.pull_request_number,
            base_sha=change.base_sha,
            head_sha=change.head_sha,
            merge_method=merge_method,
            target_branch=change.target_branch,
            change_fingerprint=change.fingerprint,
            decision_record_id=decision.decision_id,
            cer_id=cer.cer_id,
            cer_content_hash=cer.content_hash,
            policy_refs=run.policy_refs,
            expiry=expiry or cer.expires_at,
            expected_tree_sha=expected_tree_sha,
        )
        self._action_repo.put(tenant_id, action)
        run.prepared_action_fingerprint = action.fingerprint
        run.transition(WorkflowState.ACTION_PREPARED, at=at)
        scr["prepared_action"] = action
        return action

    # --- 9. ActionGate shadow evaluation + chain finalization -----------
    def evaluate_action_shadow(
        self, tenant_id: str, revision_id: str, *, at: datetime, finalize: bool = True
    ) -> ShadowActionEvaluation:
        """Evaluate the prepared action through ActionGate in shadow mode.

        ``finalize=True`` (MVP 1A default) finalizes the chain to SHADOW_COMPLETE.
        ``finalize=False`` (MVP 1B) stops at ACTION_EVALUATED so the shadow Action
        Clearance stage can run before finalization.
        """
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        action: PreparedMergeAction = scr["prepared_action"]
        evaluation = self._actiongate.evaluate_shadow(action)
        run.action_request_fingerprint = evaluation.request_fingerprint
        run.action_result_fingerprint = evaluation.result_fingerprint
        run.transition(WorkflowState.ACTION_EVALUATED, at=at)
        scr["shadow_eval"] = evaluation
        if finalize:
            # MVP 1A path: build + persist the reconstructable governance chain.
            self._finalize_chain(tenant_id, revision_id, at=at)
        return evaluation

    # --- MVP 1B: shadow Action Clearance stage --------------------------
    def record_operational_snapshot(
        self,
        tenant_id: str,
        revision_id: str,
        snapshot: CodeGovernanceOperationalSnapshot,
        *,
        projection: TrustedSignalSourceProjection,
        profile: CodeGovernanceClearanceProfile,
        at: datetime,
    ) -> None:
        """Record a supplied operational snapshot + source projection + profile.

        Transitions ACTION_EVALUATED -> CLEARANCE_PENDING. No live integration; the
        caller supplies the already-captured snapshot.
        """
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        scr["snapshot"] = snapshot
        scr["projection"] = projection
        scr["clearance_profile"] = profile
        run.transition(WorkflowState.CLEARANCE_PENDING, at=at)

    def build_trusted_signals(self, tenant_id: str, revision_id: str):
        """Build canonical TrustedSignals from the recorded snapshot (public op)."""
        scr = self._scr(tenant_id, revision_id)
        shadow_eval: ShadowActionEvaluation = scr["shadow_eval"]
        action: PreparedMergeAction = scr["prepared_action"]
        profile: CodeGovernanceClearanceProfile = scr["clearance_profile"]
        bundle = build_trusted_signals(
            scr["snapshot"], scr["projection"],
            tenant_id=tenant_id, subject_ref=action.repository,
            authorization_ref=shadow_eval.result_fingerprint,
            action_fingerprint=action.fingerprint,
            required_signal_types=profile.required_signal_types)
        scr["signal_bundle"] = bundle
        return bundle

    def evaluate_action_clearance_shadow(
        self,
        tenant_id: str,
        revision_id: str,
        *,
        evaluation_time: datetime,
        authorization_issued_at: Optional[datetime] = None,
        actor_ref: Optional[str] = None,
    ) -> ActionClearanceEvaluationRecord:
        """Evaluate Action Clearance in shadow mode for the current revision.

        Only eligible ActionGate outcomes are evaluated; an ineligible/denied
        outcome records NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED without fabricating a
        clearance result. Input/integrity problems fail closed to a terminal state.
        """
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        shadow_eval: ShadowActionEvaluation = scr["shadow_eval"]
        action: PreparedMergeAction = scr["prepared_action"]
        profile: CodeGovernanceClearanceProfile = scr["clearance_profile"]
        actor = actor_ref or getattr(scr.get("actor"), "actor_id", "unknown-actor")
        issued = authorization_issued_at or run.created_at
        rec_id = evaluation_record_id(run.revision_id, shadow_eval.result_fingerprint)

        # Upstream not authorized -> not evaluated, no fabricated clearance.
        if not is_eligible(shadow_eval):
            record = ActionClearanceEvaluationRecord(
                record_id=rec_id, tenant_id=tenant_id, workflow_id=run.workflow_id,
                workflow_revision_id=run.revision_id,
                change_fingerprint=run.change.fingerprint,
                prepared_action_fingerprint=action.fingerprint,
                stage_state=ActionClearanceStatus.NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED,
                action_request_fingerprint=shadow_eval.request_fingerprint,
                action_result_fingerprint=shadow_eval.result_fingerprint,
                actiongate_outcome=shadow_eval.outcome,
                reason_codes=("AUTHORIZATION_NOT_ELIGIBLE",) + tuple(shadow_eval.reason_codes),
                policy_refs=(profile.policy_ref,))
            self._store_clearance(tenant_id, run, record, at=evaluation_time)
            run.transition(WorkflowState.CLEARANCE_EVALUATED, at=evaluation_time)
            return record

        # Eligible -> build signals + canonical request, evaluate.
        try:
            bundle = scr.get("signal_bundle") or self.build_trusted_signals(tenant_id, revision_id)
        except ClearanceInputError:
            run.clearance_stage_state = ActionClearanceStatus.INPUT_INCOMPLETE.value
            run.transition(WorkflowState.CLEARANCE_INPUT_INCOMPLETE, at=evaluation_time)
            self._persist_snapshot(run)
            raise

        adapter = self._clearance_adapter
        try:
            authz = adapter.authorization_context(
                shadow_eval, action, actor_ref=actor, authorization_issued_at=issued)
            action_id = adapter.action_identity(action, actor_ref=actor)
            policy_ctx = adapter.policy_context(profile)
            request = adapter.build_request(
                request_id=f"cgc-{run.revision_id}", tenant_id=tenant_id,
                evaluation_time=evaluation_time, authorization=authz, action=action_id,
                signals=bundle, policy=policy_ctx, workflow_id=run.workflow_id)
            result = evaluate_clearance(request, profile.to_clearance_policy())
        except Exception as exc:  # deterministic evaluation should not raise; fail closed
            run.clearance_stage_state = ActionClearanceStatus.EVALUATION_ERROR.value
            run.transition(WorkflowState.CLEARANCE_EVALUATION_ERROR, at=evaluation_time)
            self._persist_snapshot(run)
            raise

        record = ActionClearanceEvaluationRecord(
            record_id=rec_id, tenant_id=tenant_id, workflow_id=run.workflow_id,
            workflow_revision_id=run.revision_id, change_fingerprint=run.change.fingerprint,
            prepared_action_fingerprint=action.fingerprint,
            stage_state=ActionClearanceStatus.EVALUATED,
            action_request_fingerprint=shadow_eval.request_fingerprint,
            action_result_fingerprint=shadow_eval.result_fingerprint,
            actiongate_outcome=shadow_eval.outcome,
            clearance_request_fingerprint=result.request_fingerprint,
            clearance_result_id=result.result_id,
            clearance_result_fingerprint=result.result_fingerprint,
            clearance_status=result.status.value,
            reason_codes=tuple(result.reason_codes),
            effective_constraints=tuple(result.effective_constraints),
            effective_obligations=tuple(result.obligations),
            signal_refs=tuple(result.signal_refs),
            signal_bundle_fingerprint=result.signal_bundle_fingerprint,
            clearance_policy_ref=profile.policy_ref,
            evaluated_at=result.evaluated_at, valid_until=result.valid_until,
            policy_refs=tuple(result.policy_refs))
        scr["clearance_result"] = result
        self._store_clearance(tenant_id, run, record, at=evaluation_time)
        run.transition(WorkflowState.CLEARANCE_EVALUATED, at=evaluation_time)
        return record

    def _store_clearance(self, tenant_id: str, run: WorkflowRun,
                         record: ActionClearanceEvaluationRecord, *, at: datetime) -> None:
        self._clearance_eval_repo[(tenant_id, record.record_id)] = record
        self._scr(tenant_id, run.revision_id)["clearance_record"] = record
        run.clearance_stage_state = record.stage_state.value
        run.clearance_evaluation_ref = record.record_id
        run.clearance_result_id = record.clearance_result_id or None
        run.clearance_status = record.clearance_status or None

    def assess_human_intervention(
        self,
        tenant_id: str,
        revision_id: str,
        *,
        at: datetime,
        routing: Optional[InterventionRoutingPolicy] = None,
        sensitive: bool = False,
    ) -> HumanInterventionAssessment:
        """Deterministically route clearance reasons to an intervention assessment.

        Advisory/routing metadata only — never a binding decision. Then finalizes
        the extended governance chain to SHADOW_COMPLETE.
        """
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        record: ActionClearanceEvaluationRecord = scr["clearance_record"]
        profile: CodeGovernanceClearanceProfile = scr["clearance_profile"]
        routing = routing or InterventionRoutingPolicy()
        # Choose the routing status: canonical clearance status when evaluated, else
        # a fail-closed BLOCK for the upstream-not-authorized case.
        if record.stage_state is ActionClearanceStatus.EVALUATED:
            status = ClearanceStatus(record.clearance_status)
            reason_codes = record.reason_codes
        else:
            status = ClearanceStatus.BLOCK
            reason_codes = ("AUTHORIZATION_NOT_ELIGIBLE",)
        assessment = assess_intervention(
            tenant_id=tenant_id, workflow_id=run.workflow_id,
            workflow_revision_id=run.revision_id, clearance_status=status,
            reason_codes=reason_codes, signal_refs=record.signal_refs,
            profile=profile, routing=routing, claim_refs=(run.claim_manifest_id or "",),
            sensitive=sensitive)
        self._intervention_repo[(tenant_id, assessment.assessment_id)] = assessment
        scr["intervention"] = assessment
        run.intervention_assessment_ref = assessment.assessment_id
        run.human_intervention_required = bool(assessment.required)
        run.transition(WorkflowState.INTERVENTION_ASSESSED, at=at)
        self._finalize_chain(tenant_id, revision_id, at=at)
        return assessment

    def get_clearance_evaluation(self, tenant_id: str, record_id: str):
        return self._clearance_eval_repo.get((tenant_id, record_id))

    def get_intervention_assessment(self, tenant_id: str, assessment_id: str):
        return self._intervention_repo.get((tenant_id, assessment_id))

    def _finalize_chain(self, tenant_id: str, revision_id: str, *, at: datetime) -> None:
        run = self._run(tenant_id, revision_id)
        scr = self._scr(tenant_id, revision_id)
        cid = chain_id_for(run.workflow_id, run.revision_id)
        cev: Optional[ActionClearanceEvaluationRecord] = scr.get("clearance_record")
        hia: Optional[HumanInterventionAssessment] = scr.get("intervention")
        chain = GovernanceChainRecord(
            chain_id=cid,
            workflow_id=run.workflow_id,
            revision_id=run.revision_id,
            tenant_id=tenant_id,
            repository=run.change.repository,
            pull_request_number=run.change.pull_request_number,
            change_fingerprint=run.change.fingerprint,
            base_sha=run.change.base_sha,
            head_sha=run.change.head_sha,
            evidence_refs=tuple(run.evidence_ids),
            claim_manifest_ref=run.claim_manifest_id or "",
            claim_manifest_fingerprint=run.claim_manifest_fingerprint or "",
            tap_request_fingerprints=run.tap_request_fingerprints,
            tap_result_fingerprints=run.tap_result_fingerprints,
            recommendation_ref=run.recommendation_id,
            decision_record_id=run.decision_record_id or "",
            cer_id=run.cer_id or "",
            cer_content_hash=run.cer_content_hash or "",
            prepared_action_ref=run.prepared_action_fingerprint or "",
            action_request_fingerprint=run.action_request_fingerprint or "",
            action_result_fingerprint=run.action_result_fingerprint or "",
            workflow_mode=WorkflowMode.SHADOW,
            created_at=run.created_at,
            evaluated_at=at,
            policy_refs=run.policy_refs,
            action_clearance_status=(cev.stage_state if cev
                                     else ActionClearanceStatus.NOT_EVALUATED),
            clearance_evaluation_ref=(cev.record_id if cev else ""),
            clearance_evaluation_fingerprint=(cev.fingerprint if cev else ""),
            clearance_request_fingerprint=(cev.clearance_request_fingerprint if cev else ""),
            clearance_result_id=(cev.clearance_result_id if cev else ""),
            clearance_result_fingerprint=(cev.clearance_result_fingerprint if cev else ""),
            clearance_status=(cev.clearance_status if cev else ""),
            clearance_reason_codes=(cev.reason_codes if cev else ()),
            clearance_signal_refs=(cev.signal_refs if cev else ()),
            clearance_signal_bundle_fingerprint=(cev.signal_bundle_fingerprint if cev else ""),
            clearance_policy_ref=(cev.clearance_policy_ref if cev else ""),
            clearance_evaluated_at=(cev.evaluated_at if cev else None),
            clearance_valid_until=(cev.valid_until if cev else None),
            clearance_effective_constraints=(cev.effective_constraints if cev else ()),
            clearance_effective_obligations=(cev.effective_obligations if cev else ()),
            intervention_assessment_ref=(hia.assessment_id if hia else ""),
            intervention_assessment_fingerprint=(hia.fingerprint if hia else ""),
            human_intervention_required=(bool(hia.required) if hia else False),
            required_authorities=(hia.required_authorities if hia else ()),
        )
        # Fail closed if any mandatory link is missing.
        missing = [
            name for name, val in (
                ("evidence", run.evidence_ids),
                ("claim_manifest", run.claim_manifest_id),
                ("tap_results", run.tap_result_fingerprints),
                ("decision", run.decision_record_id),
                ("cer", run.cer_id),
                ("prepared_action", run.prepared_action_fingerprint),
                ("action_result", run.action_result_fingerprint),
            ) if not val
        ]
        if missing:
            run.transition(WorkflowState.CHAIN_INCOMPLETE, at=at)
            self._persist_snapshot(run)
            return
        self._chain_repo.put(chain)
        run.chain_id = cid
        run.transition(WorkflowState.SHADOW_COMPLETE, at=at)
        self._persist_snapshot(run)

    # --- 10. reconstruction ---------------------------------------------
    def reconstruct_chain(self, tenant_id: str, revision_id: str) -> ReconstructionResult:
        run = self._runs.get((tenant_id, revision_id))
        if run is None or run.chain_id is None:
            # No chain finalized — reconstruct by the deterministic chain id.
            from .workflow.records import workflow_id_for, revision_id_for  # local
            raise RecordNotFoundError(
                f"no finalized governance chain for revision {revision_id}")
        current_head = self._current_head.get(run.workflow_id)
        return self._reconstruction.reconstruct(
            tenant_id, run.chain_id, current_head_sha=current_head)

    # --- 11. read-only projections --------------------------------------
    def get_workflow(self, tenant_id: str, revision_id: str):
        """Return the live workflow revision snapshot."""
        run = self._runs.get((tenant_id, revision_id))
        if run is not None:
            return run.snapshot()
        persisted = self._workflow_repo.get(tenant_id, revision_id)
        if persisted is None:
            raise RecordNotFoundError(f"no workflow for revision {revision_id}")
        return persisted

    def get_governance_chain(self, tenant_id: str, chain_id: str) -> Optional[GovernanceChainRecord]:
        return self._chain_repo.get(tenant_id, chain_id)

    def execution_status(self) -> str:
        """Execution is disabled in MVP 1A. Always returns ``DISABLED``."""
        return ExecutionStatus.DISABLED.value


__all__ = ["CodeGovernanceService"]
