"""Shadow-only cloud ACP adapter (V2 §8).

Orchestrates one cloud decision end-to-end, reusing the **frozen ACP core
unchanged**:

    real cluster state  ->  CloudConstraintEvaluator  (real cloud_controller)
                        ->  filter_admissible + LexicographicActionSelector (core)
                        ->  DecisionTrace                                   (core)
                        ->  cloud_recommendation                            (§7)
                        ->  compose(ActionGate verdict, ACP rec)            (§3/§13)

Safety posture (all enforced here):
* **OFF by default** (``enabled=False``) — a disabled adapter does no work and
  returns ``None``; nothing is recorded. This is the kill switch.
* **Never actuates.** No Kubernetes client, no ActionGate token minted, no
  Deployment patched. Every record is ``shadow_only=True``.
* **Contained exceptions.** Any failure inside shadow evaluation is caught,
  recorded as ``shadow_error``, and never propagates to a caller (a real control
  loop must be unaffected by the shadow).
* **Bounded logging.** A fixed-capacity ring buffer (``deque(maxlen)``) — no
  unbounded growth / DoS path; drops are counted.
* **Commit-time revalidation.** Reuses the frozen ``ReferenceCommitRevalidator``
  to detect cluster drift between decision and commit (TOCTOU). The reference
  authorization object is a content-identity binding used ONLY for revalidation;
  ACP never mints a real execution credential — that is ActionGate's job.

Stdlib-only.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Mapping, Optional, Sequence, Tuple

from ..action_selection import LexicographicActionSelector
from ..authorization import ReferenceCommitRevalidator
from ..envelopes import ActionDecision
from ..errors import ACPError
from .composition import (
    AuthorizationVerdict,
    CombinedOutcome,
    CompositionResult,
    compose,
)
from .constraints import CloudConstraintConfig, CloudConstraintEvaluator
from .envelopes import (
    CloudActionCandidate,
    CloudOperationalEvidence,
    CloudWorldState,
)
from .outcomes import CloudRecommendation, cloud_recommendation

_EVALUATOR = "acp.cloud.CloudShadowAdapter"


@dataclass(frozen=True)
class CloudShadowRecord:
    """Immutable out-of-band record of one shadow cloud decision."""
    decision_id: str
    world_state_version: str
    considered_candidate_ids: Tuple[str, ...]
    acp_decision: ActionDecision
    selected_candidate_id: Optional[str]
    selected_action_identity: Optional[str]
    cloud_recommendation: CloudRecommendation
    authorization_verdict: Optional[AuthorizationVerdict]
    combined_outcome: Optional[CombinedOutcome]
    reason_codes: Tuple[str, ...]
    shadow_only: bool = True
    shadow_error: bool = False
    error_kind: str = field(default="")

    def content_dict(self) -> dict:
        """Deterministic content (excludes nothing time-varying — all fields are
        deterministic functions of inputs)."""
        return {
            "decision_id": self.decision_id,
            "world_state_version": self.world_state_version,
            "considered_candidate_ids": list(self.considered_candidate_ids),
            "acp_decision": self.acp_decision.value,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_action_identity": self.selected_action_identity,
            "cloud_recommendation": self.cloud_recommendation.value,
            "authorization_verdict": (
                self.authorization_verdict.value
                if self.authorization_verdict is not None else None),
            "combined_outcome": (
                self.combined_outcome.value
                if self.combined_outcome is not None else None),
            "reason_codes": list(self.reason_codes),
            "shadow_only": self.shadow_only,
            "shadow_error": self.shadow_error,
            "error_kind": self.error_kind,
        }


class BoundedCloudSink:
    """Fixed-capacity ring buffer (reuses the robotics bounded-sink pattern)."""

    def __init__(self, maxlen: int = 10000):
        self._buf: Deque[CloudShadowRecord] = deque(maxlen=maxlen)
        self._dropped = 0
        self._seen = 0

    def append(self, record: CloudShadowRecord) -> None:
        self._seen += 1
        if self._buf.maxlen is not None and len(self._buf) == self._buf.maxlen:
            self._dropped += 1  # this append evicts the oldest
        self._buf.append(record)

    @property
    def records(self) -> Tuple[CloudShadowRecord, ...]:
        return tuple(self._buf)

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def seen(self) -> int:
        return self._seen


@dataclass(frozen=True)
class CloudShadowResult:
    """Full result of one shadow evaluation (returned when enabled)."""
    decision_id: str
    acp_decision: ActionDecision
    cloud_recommendation: CloudRecommendation
    composition: Optional[CompositionResult]
    evidence: Mapping[str, CloudOperationalEvidence]
    record: CloudShadowRecord


def _blast_sort_key(c: CloudActionCandidate) -> tuple:
    """Frozen total order for cloud candidates: smallest operational blast first,
    then destructive last, then id (appended by the selector)."""
    return (c.blast_radius, 1 if c.is_destructive else 0, c.operation.value)


class CloudShadowAdapter:
    """Out-of-band ACP shadow evaluation of a cloud operation. OFF by default."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        sink: Optional[BoundedCloudSink] = None,
        config: Optional[CloudConstraintConfig] = None,
        max_freshness_s: Optional[float] = None,
    ) -> None:
        self.enabled = enabled
        self.sink = sink or BoundedCloudSink()
        self._evaluator = CloudConstraintEvaluator(config)
        self._selector = LexicographicActionSelector(sort_key=_blast_sort_key)
        self._revalidator = ReferenceCommitRevalidator()

    def observe(
        self,
        *,
        decision_id: str,
        world: Optional[CloudWorldState],
        candidates: Sequence[CloudActionCandidate],
        now_s: float,
        freshness_s: float,
        authorization: Optional[AuthorizationVerdict] = None,
        tick: int = 0,
    ) -> Optional[CloudShadowResult]:
        """Evaluate one cloud decision out-of-band.

        Returns ``None`` when disabled (kill switch) — no work, no record. When
        enabled, always returns a result and appends exactly one record; any
        internal failure is contained and surfaced as ``shadow_error`` rather
        than raised.
        """
        if not self.enabled:
            return None
        try:
            return self._observe(
                decision_id=decision_id, world=world, candidates=candidates,
                now_s=now_s, freshness_s=freshness_s,
                authorization=authorization, tick=tick)
        except Exception as exc:  # contained: shadow must never break a caller
            record = CloudShadowRecord(
                decision_id=decision_id,
                world_state_version=(world.version if world is not None else ""),
                considered_candidate_ids=tuple(c.candidate_id for c in candidates),
                acp_decision=ActionDecision.NO_SAFE_ACTION,
                selected_candidate_id=None,
                selected_action_identity=None,
                cloud_recommendation=CloudRecommendation.HOLD,
                authorization_verdict=authorization,
                combined_outcome=None,
                reason_codes=(f"SHADOW_ERROR:{type(exc).__name__}",),
                shadow_error=True,
                error_kind=type(exc).__name__,
            )
            self.sink.append(record)
            return CloudShadowResult(
                decision_id=decision_id,
                acp_decision=ActionDecision.NO_SAFE_ACTION,
                cloud_recommendation=CloudRecommendation.HOLD,
                composition=None, evidence={}, record=record)

    def _observe(
        self,
        *,
        decision_id: str,
        world: Optional[CloudWorldState],
        candidates: Sequence[CloudActionCandidate],
        now_s: float,
        freshness_s: float,
        authorization: Optional[AuthorizationVerdict],
        tick: int,
    ) -> CloudShadowResult:
        evidence: Dict[str, CloudOperationalEvidence] = {}
        constraints: Dict[str, Tuple] = {}
        for c in candidates:
            ev, results = self._evaluator.evaluate(
                c, world, now_s=now_s, freshness_s=freshness_s)
            evidence[c.candidate_id] = ev
            constraints[c.candidate_id] = results

        # Frozen core selector — unchanged — over cloud envelopes.
        if world is None:
            # No state => cannot bind a decision trace; fail closed to HOLD.
            record = CloudShadowRecord(
                decision_id=decision_id, world_state_version="",
                considered_candidate_ids=tuple(c.candidate_id for c in candidates),
                acp_decision=ActionDecision.NO_SAFE_ACTION,
                selected_candidate_id=None, selected_action_identity=None,
                cloud_recommendation=CloudRecommendation.HOLD,
                authorization_verdict=authorization, combined_outcome=(
                    compose(authorization, CloudRecommendation.HOLD).combined
                    if authorization is not None else None),
                reason_codes=("STATE_MISSING",))
            self.sink.append(record)
            return CloudShadowResult(
                decision_id=decision_id,
                acp_decision=ActionDecision.NO_SAFE_ACTION,
                cloud_recommendation=CloudRecommendation.HOLD,
                composition=(compose(authorization, CloudRecommendation.HOLD)
                             if authorization is not None else None),
                evidence=evidence, record=record)

        outcome = self._selector.select(
            tick=tick, decision_id=decision_id, world_state=world,
            candidates=list(candidates), candidate_constraints=constraints)

        rec = cloud_recommendation(outcome.decision)
        composition = (compose(authorization, rec)
                       if authorization is not None else None)

        # Collect dispositive reason codes from the trace's rejections.
        reason_codes = tuple(r.reason_code for r in outcome.trace.rejected)

        record = CloudShadowRecord(
            decision_id=decision_id,
            world_state_version=world.version,
            considered_candidate_ids=outcome.trace.candidate_ids_considered,
            acp_decision=outcome.decision,
            selected_candidate_id=outcome.trace.selected_candidate_id,
            selected_action_identity=outcome.trace.selected_action_identity,
            cloud_recommendation=rec,
            authorization_verdict=authorization,
            combined_outcome=(composition.combined
                              if composition is not None else None),
            reason_codes=reason_codes,
        )
        self.sink.append(record)
        return CloudShadowResult(
            decision_id=decision_id, acp_decision=outcome.decision,
            cloud_recommendation=rec, composition=composition,
            evidence=evidence, record=record)

    # ---- commit-time revalidation (TOCTOU) ------------------------------
    def commit_revalidate(
        self,
        *,
        decision_id: str,
        selected: CloudActionCandidate,
        world_at_decision: CloudWorldState,
        constraint_set_version: str,
        current_world: CloudWorldState,
        current_constraint_set_version: str,
        issued_time_s: float,
        now_s: float,
        ttl_s: float = 5.0,
        current_candidate: Optional[CloudActionCandidate] = None,
    ) -> Tuple[bool, str]:
        """Return ``(still_valid, reason)`` by reusing the frozen revalidator.

        The authorization is bound to ``selected`` (the candidate ACP decided on
        at decision time). At commit time we revalidate against
        ``current_candidate`` (defaults to ``selected``) and ``current_world``.
        This detects cluster drift (resourceVersion / state change), candidate
        rebinding (e.g. a manifest digest mutated after the decision), and
        expiry. Shadow-only: this gates nothing; it records whether the earlier
        recommendation still holds.
        """
        from ..authorization import ControlAuthorization

        auth = ControlAuthorization(
            decision_id=decision_id,
            action_identity=selected.identity,
            world_state_version=world_at_decision.version,
            constraint_set_version=constraint_set_version,
            decision=ActionDecision.EXECUTE,
            issued_time_s=issued_time_s,
            expiry_time_s=issued_time_s + ttl_s,
        )
        try:
            self._revalidator.revalidate(
                authorization=auth, candidate=current_candidate or selected,
                current_world_state=current_world,
                current_constraint_set_version=current_constraint_set_version,
                now_s=now_s)
            return True, "still valid"
        except ACPError as exc:
            return False, f"{type(exc).__name__}: {exc}"
