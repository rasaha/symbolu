"""Integrated ActionGate + ACP shadow harness for Kubernetes (V2.1 §7, §8).

Runs BOTH real layers on ONE identity-bound Kubernetes operation, composes their
verdicts, and records a deterministic shadow record — OFF by default, never
mutating a cluster, never propagating an exception, with bounded logging and a
kill switch.

  op -> run_actiongate (REAL ActionGate)     ─┐
     -> CloudShadowAdapter  (REAL ACP core + real cloud_controller) ─┤
     -> bind() identity check                 ─┤ compose() -> CompositionClass
     -> commit_revalidate (both layers)        ┘

Neither layer is authoritative; no execution token is minted or consumed; no
Kubernetes API call is made (a real cluster is infeasible offline — see
`LIVE_K8S_SHADOW_METHOD.md`).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple

from symbolu_robotics.autonomous_control_plane.cloud import (
    CloudShadowAdapter,
    CloudValidity,
    CloudRecommendation,
)
from robotics_reliability_bench.acp_k8s_integrated.actiongate_runner import (
    ActionGateResult,
    current_state_hash,
    run_actiongate,
)
from robotics_reliability_bench.acp_k8s_integrated.composition import (
    CompositionClass,
    CompositionOutcome,
    compose,
)
from robotics_reliability_bench.acp_k8s_integrated.identity_binding import (
    KubernetesOperation,
    bind,
    build_cloud_candidate,
    build_cloud_world,
)

_NOW_S = 0.0  # fixed observation clock for ACP (deterministic)


@dataclass(frozen=True)
class CommitDrift:
    """Optional drift injected between evaluation and hypothetical commit (§8)."""
    new_resource_version: Optional[str] = None
    mutated_manifest_digest: Optional[str] = None
    new_policy_version: Optional[str] = None


@dataclass(frozen=True)
class CommitRevalidation:
    """Which layer(s) reject a drift at commit time."""
    checked: bool
    still_valid: bool
    actiongate_rejects: bool
    acp_rejects: bool
    reason: str


@dataclass(frozen=True)
class IntegratedRecord:
    """Immutable, deterministic record of one integrated shadow evaluation."""
    scenario_id: str
    composition_class: str
    authorization_outcome: Optional[str]
    authorization_dispositive: Tuple[str, ...]
    acp_decision: Optional[str]
    acp_recommendation: Optional[str]
    acp_validity: Optional[str]
    identity_bound: bool
    identity_reason: str
    composition_identity: Optional[str]
    actiongate_action_hash: Optional[str]
    acp_candidate_identity: Optional[str]
    shared_operation_digest: Optional[str]
    shared_state_version: Optional[str]
    hypothetically_eligible: bool
    commit_revalidation: Optional[dict]
    shadow_only: bool = True
    shadow_error: bool = False
    error_kind: str = ""
    cluster_mutated: bool = False       # ALWAYS False — proven, never set True

    def content_dict(self) -> dict:
        d = dict(self.__dict__)
        d["authorization_dispositive"] = list(self.authorization_dispositive)
        return d


@dataclass(frozen=True)
class IntegratedResult:
    scenario_id: str
    composition: CompositionOutcome
    actiongate: Optional[ActionGateResult]
    record: IntegratedRecord


class BoundedIntegratedSink:
    """Fixed-capacity ring buffer (bounded logging; drops counted)."""

    def __init__(self, maxlen: int = 10000):
        self._buf: Deque[IntegratedRecord] = deque(maxlen=maxlen)
        self._dropped = 0
        self._seen = 0

    def append(self, record: IntegratedRecord) -> None:
        self._seen += 1
        if self._buf.maxlen is not None and len(self._buf) == self._buf.maxlen:
            self._dropped += 1
        self._buf.append(record)

    @property
    def records(self) -> Tuple[IntegratedRecord, ...]:
        return tuple(self._buf)

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def seen(self) -> int:
        return self._seen


class IntegratedShadowHarness:
    """Composes real ActionGate + real ACP on one K8s op. OFF by default."""

    def __init__(self, *, enabled: bool = False,
                 sink: Optional[BoundedIntegratedSink] = None,
                 allowed_namespaces=("protected",)) -> None:
        self.enabled = enabled
        self.sink = sink or BoundedIntegratedSink()
        self._allowed = tuple(allowed_namespaces)
        self._acp = CloudShadowAdapter(enabled=True)   # inner ACP always runs when we do

    def evaluate(
        self,
        op: KubernetesOperation,
        *,
        scenario_id: str,
        freshness_s: float = 1.0,
        ag_overrides: Optional[dict] = None,
        acp_manifest_digest_override: Optional[str] = None,
        commit_drift: Optional[CommitDrift] = None,
        inject_shadow_error: bool = False,
    ) -> Optional[IntegratedResult]:
        """Evaluate one operation through both layers + composition.

        Returns ``None`` when disabled (kill switch). Otherwise always returns a
        result and records exactly one row; any internal failure is contained
        and surfaced as ``SHADOW_ERROR``. ``inject_shadow_error`` deliberately
        raises inside the pipeline to exercise the containment path (corpus
        evaluator-exception scenario).
        """
        if not self.enabled:
            return None
        try:
            if inject_shadow_error:
                raise RuntimeError("injected evaluator exception")
            return self._evaluate(
                op, scenario_id=scenario_id, freshness_s=freshness_s,
                ag_overrides=ag_overrides or {},
                acp_manifest_digest_override=acp_manifest_digest_override,
                commit_drift=commit_drift)
        except Exception as exc:  # contained: shadow must never break a caller
            comp = compose(
                identity_bound=True, identity_reason="", authorization_outcome=None,
                is_authorized=False, is_denied=False, is_pending=False,
                acp_recommendation=None, acp_validity=None,
                shadow_error=True, error_kind=type(exc).__name__)
            rec = IntegratedRecord(
                scenario_id=scenario_id,
                composition_class=comp.composition_class.value,
                authorization_outcome=None, authorization_dispositive=(),
                acp_decision=None, acp_recommendation=None, acp_validity=None,
                identity_bound=True, identity_reason="",
                composition_identity=None, actiongate_action_hash=None,
                acp_candidate_identity=None, shared_operation_digest=None,
                shared_state_version=None, hypothetically_eligible=False,
                commit_revalidation=None, shadow_error=True,
                error_kind=type(exc).__name__)
            self.sink.append(rec)
            return IntegratedResult(scenario_id, comp, None, rec)

    def _evaluate(self, op, *, scenario_id, freshness_s, ag_overrides,
                  acp_manifest_digest_override, commit_drift) -> IntegratedResult:
        # --- real ActionGate ---
        ag = run_actiongate(
            namespace=op.namespace, name=op.deployment, k8s_verb=op.k8s_verb,
            replicas=(0 if op.k8s_verb == "DELETE" else op.desired_replicas),
            resource_version=op.resource_version,
            allowed_namespaces=self._allowed,
            compliant_manifest=op.compliant_manifest,
            rollback_plan=({"to": op.rollback_ref} if op.rollback_ref else None),
            **ag_overrides)

        # --- real ACP (frozen core + real cloud_controller) ---
        world = build_cloud_world(op)
        candidate = build_cloud_candidate(
            op, world, manifest_digest_override=acp_manifest_digest_override)
        acp_result = self._acp.observe(
            decision_id=scenario_id, world=world, candidates=[candidate],
            now_s=_NOW_S, freshness_s=freshness_s, authorization=None)
        acp_rec = acp_result.cloud_recommendation
        acp_evidence = acp_result.evidence.get(candidate.candidate_id)
        acp_validity = acp_evidence.validity if acp_evidence else CloudValidity.MISSING

        # --- identity binding ---
        ident, reason = bind(op, ag, candidate, world)
        bound = ident is not None

        # --- composition ---
        comp = compose(
            identity_bound=bound, identity_reason=reason,
            authorization_outcome=ag.outcome, is_authorized=ag.is_authorized,
            is_denied=ag.is_denied, is_pending=ag.is_pending,
            acp_recommendation=acp_rec, acp_validity=acp_validity)

        # --- commit-time revalidation (§8) ---
        reval = None
        if commit_drift is not None:
            reval = self._commit_revalidate(op, ag, candidate, world, commit_drift)

        rec = IntegratedRecord(
            scenario_id=scenario_id,
            composition_class=comp.composition_class.value,
            authorization_outcome=ag.outcome,
            authorization_dispositive=ag.dispositive_rules,
            acp_decision=acp_result.acp_decision.value,
            acp_recommendation=acp_rec.value, acp_validity=acp_validity.value,
            identity_bound=bound, identity_reason=reason,
            composition_identity=(ident.identity if ident else None),
            actiongate_action_hash=ag.action_hash,
            acp_candidate_identity=candidate.identity,
            shared_operation_digest=(ident.shared_operation_digest if ident else None),
            shared_state_version=(ident.shared_state_version if ident else None),
            hypothetically_eligible=comp.hypothetically_eligible,
            commit_revalidation=(reval.__dict__ if reval else None))
        self.sink.append(rec)
        return IntegratedResult(scenario_id, comp, ag, rec)

    # ---- commit-time revalidation: which layer rejects drift? ----
    def _commit_revalidate(self, op, ag: ActionGateResult, candidate, world,
                           drift: CommitDrift) -> CommitRevalidation:
        ag_rejects = False
        reasons = []

        # ActionGate rejects: resourceVersion drift (state hash), patch mutation
        # (action hash), or policy-version change.
        if drift.new_resource_version is not None:
            new_csh = current_state_hash(op.namespace, op.deployment,
                                         drift.new_resource_version)
            if new_csh != ag.current_state_hash:
                ag_rejects = True
                reasons.append("ActionGate:E_STALE_STATE(resourceVersion)")
        if (drift.mutated_manifest_digest is not None
                and drift.mutated_manifest_digest != ag.manifest_digest):
            ag_rejects = True
            reasons.append("ActionGate:ACTION_HASH_MISMATCH(patch)")
        if (drift.new_policy_version is not None
                and drift.new_policy_version != ag.policy_version):
            ag_rejects = True
            reasons.append("ActionGate:POLICY_MISMATCH")

        # ACP rejects via the FROZEN ReferenceCommitRevalidator: state drift or
        # candidate (patch) mutation.
        acp_rejects = False
        current_world = world
        current_candidate = None
        if drift.new_resource_version is not None:
            current_world = build_cloud_world(
                _with_rv(op, drift.new_resource_version))
        if drift.mutated_manifest_digest is not None:
            current_candidate = build_cloud_candidate(
                op, world, manifest_digest_override=drift.mutated_manifest_digest)
        still_valid_acp, acp_reason = self._acp.commit_revalidate(
            decision_id="commit", selected=candidate, world_at_decision=world,
            constraint_set_version="cs-1", current_world=current_world,
            current_constraint_set_version="cs-1", issued_time_s=_NOW_S,
            now_s=_NOW_S + 1.0, current_candidate=current_candidate)
        if not still_valid_acp:
            acp_rejects = True
            reasons.append(f"ACP:{acp_reason}")

        still_valid = not (ag_rejects or acp_rejects)
        return CommitRevalidation(
            checked=True, still_valid=still_valid, actiongate_rejects=ag_rejects,
            acp_rejects=acp_rejects, reason="; ".join(reasons) or "no drift")


def _with_rv(op: KubernetesOperation, rv: str) -> KubernetesOperation:
    from dataclasses import replace
    return replace(op, resource_version=rv)
