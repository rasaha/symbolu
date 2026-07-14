"""Disabled-by-default shadow hook around a live planner (Phase 3 §4, §7).

Wraps a REAL planner by composition (no production edit): ``InstrumentedTaskPlanner``
returns the real planner's ``Plan`` byte-identically and, only when the hook is
ENABLED, records an out-of-band ACP shadow evaluation of that plan. The hook:

  * defaults OFF (``enabled=False``);
  * never alters the returned plan and never changes the planner's exception
    behaviour;
  * contains ALL its own exceptions -> a shadow failure cannot block or alter the
    authoritative path (records ``shadow_error=True`` instead);
  * writes to a BOUNDED ring buffer so shadow logging cannot create a DoS path;
  * produces records explicitly marked ``shadow_only=True``;
  * never reaches an actuator/controller.

Commit-time revalidation (§7) is provided for the harness to check, before the
runtime would send the action, whether the earlier ACP evaluation would still be
valid (world/trajectory identity unchanged, evidence fresh). It does NOT gate
execution.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple

import numpy as np

from ..action_selection import LexicographicActionSelector
from ..envelopes import ActionDecision
from ..errors import AuthorizationBindingError, StaleAuthorizationError
from ..world_state import CanonicalWorldState
from .live_planner_adapter import (LivePathResult, LivePathStatus,
                                    plan_to_trajectory_candidate)
from .trajectory_adapter import TrajectoryValidatorAdapter


@dataclass(frozen=True)
class ShadowRecord3:
    action_id: str
    world_state_identity: str
    candidate_identity: Optional[str]
    planner_provenance: str
    live_status: str
    physical_validity: Optional[str]
    is_safe: Optional[bool]
    acp_decision: str
    acp_admissible: bool
    dispositive_reasons: Tuple[str, ...]
    safety_score: Optional[float]
    ttc_s: Optional[float]
    adapter_latency_us: float
    validator_latency_us: float
    total_shadow_latency_us: float
    shadow_error: bool
    shadow_only: bool = field(default=True)

    def content_dict(self) -> dict:
        """Deterministic content (excludes wall-clock latencies)."""
        return {
            "action_id": self.action_id,
            "world_state_identity": self.world_state_identity,
            "candidate_identity": self.candidate_identity,
            "planner_provenance": self.planner_provenance,
            "live_status": self.live_status,
            "physical_validity": self.physical_validity,
            "is_safe": self.is_safe,
            "acp_decision": self.acp_decision,
            "acp_admissible": self.acp_admissible,
            "dispositive_reasons": list(self.dispositive_reasons),
            "safety_score": self.safety_score,
            "ttc_s": self.ttc_s,
            "shadow_error": self.shadow_error,
            "shadow_only": self.shadow_only,
        }

    def to_dict(self) -> dict:
        d = self.content_dict()
        d.update(adapter_latency_us=round(self.adapter_latency_us, 3),
                 validator_latency_us=round(self.validator_latency_us, 3),
                 total_shadow_latency_us=round(self.total_shadow_latency_us, 3))
        return d


class BoundedShadowSink:
    """Fixed-capacity ring buffer. Oldest records drop; logging cannot grow
    unbounded (no DoS path)."""

    def __init__(self, maxlen: int = 1000):
        self._buf: Deque[ShadowRecord3] = deque(maxlen=maxlen)
        self._dropped = 0
        self._seen = 0

    def append(self, record: ShadowRecord3) -> None:
        self._seen += 1
        if len(self._buf) == self._buf.maxlen:
            self._dropped += 1  # this append evicts the oldest
        self._buf.append(record)

    @property
    def records(self) -> Tuple[ShadowRecord3, ...]:
        return tuple(self._buf)

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def seen(self) -> int:
        return self._seen


class ShadowPlannerHook:
    """Out-of-band ACP shadow evaluation of a real plan. Disabled by default."""

    def __init__(self, *, sink: Optional[BoundedShadowSink] = None,
                 enabled: bool = False,
                 validator_adapter: Optional[TrajectoryValidatorAdapter] = None,
                 dt: float = 0.1, steps: int = 5, max_stale_s: float = 0.2):
        self.enabled = enabled
        self.sink = sink or BoundedShadowSink()
        self._adapter = validator_adapter or TrajectoryValidatorAdapter(
            max_stale_s=max_stale_s)
        self._selector = LexicographicActionSelector(lambda c: (0,))
        self._dt = dt
        self._steps = steps
        # keep last evidence for commit-time revalidation (bounded to 1)
        self._last: Optional[dict] = None

    def observe(self, *, action_id: str, plan, world_state: CanonicalWorldState,
                q0: np.ndarray, obstacles=None, human_position=None,
                freshness_s: float = 0.01, now_s: float = 0.0
                ) -> Optional[ShadowRecord3]:
        """Record an ACP shadow evaluation of ``plan``. Never raises."""
        if not self.enabled:
            return None
        t0 = time.perf_counter()
        try:
            return self._observe_inner(action_id, plan, world_state, q0, obstacles,
                                       human_position, freshness_s, now_s, t0)
        except Exception:  # noqa: BLE001 - a shadow failure must never escape
            rec = ShadowRecord3(
                action_id=action_id, world_state_identity=world_state.version,
                candidate_identity=None, planner_provenance="unknown",
                live_status="SHADOW_ERROR", physical_validity=None, is_safe=None,
                acp_decision="SHADOW_ERROR", acp_admissible=False,
                dispositive_reasons=("SHADOW_ERROR",), safety_score=None, ttc_s=None,
                adapter_latency_us=0.0, validator_latency_us=0.0,
                total_shadow_latency_us=(time.perf_counter() - t0) * 1e6,
                shadow_error=True)
            self.sink.append(rec)
            return rec

    def _observe_inner(self, action_id, plan, world_state, q0, obstacles,
                       human_position, freshness_s, now_s, t0) -> ShadowRecord3:
        ta = time.perf_counter()
        live: LivePathResult = plan_to_trajectory_candidate(
            action_id=action_id, plan=plan, world_version=world_state.version,
            q0=q0, dt=self._dt, steps=self._steps,
            planner_provenance="deliberative.TaskPlanner")
        adapter_us = (time.perf_counter() - ta) * 1e6

        if live.status is not LivePathStatus.SUPPORTED:
            # fail-closed: unsupported/missing/malformed -> not admissible
            rec = ShadowRecord3(
                action_id=action_id, world_state_identity=world_state.version,
                candidate_identity=None, planner_provenance=live.planner_provenance,
                live_status=live.status.value, physical_validity=None, is_safe=None,
                acp_decision=ActionDecision.NO_SAFE_ACTION.value, acp_admissible=False,
                dispositive_reasons=(live.status.value,), safety_score=None, ttc_s=None,
                adapter_latency_us=adapter_us, validator_latency_us=0.0,
                total_shadow_latency_us=(time.perf_counter() - t0) * 1e6,
                shadow_error=False)
            self.sink.append(rec)
            self._last = None
            return rec

        tv = time.perf_counter()
        ev, results = self._adapter.evaluate(
            candidate=live.candidate, trajectory_points=live.trajectory_points,
            obstacles=obstacles, human_position=human_position,
            world_version=world_state.version, now_s=now_s,
            observation_time_s=now_s, freshness_s=freshness_s)
        validator_us = (time.perf_counter() - tv) * 1e6

        outcome = self._selector.select(
            tick=0, decision_id=action_id, world_state=world_state,
            candidates=[live.candidate], candidate_constraints={live.candidate.candidate_id: results})
        admissible = outcome.selected is not None
        rec = ShadowRecord3(
            action_id=action_id, world_state_identity=world_state.version,
            candidate_identity=live.candidate.identity,
            planner_provenance=live.planner_provenance, live_status=live.status.value,
            physical_validity=ev.validity.value, is_safe=ev.is_safe,
            acp_decision=outcome.decision.value, acp_admissible=admissible,
            dispositive_reasons=tuple(r.reason_code for r in outcome.trace.rejected),
            safety_score=ev.safety_score, ttc_s=ev.time_to_collision_s,
            adapter_latency_us=adapter_us, validator_latency_us=validator_us,
            total_shadow_latency_us=(time.perf_counter() - t0) * 1e6, shadow_error=False)
        self.sink.append(rec)
        self._last = {"candidate": live.candidate, "world_version": world_state.version,
                      "constraint_set_version": "cs-1"}
        return rec

    def commit_revalidate(self, *, candidate, current_world_state, now_s,
                          max_stale_s: float = 0.2, evidence_time_s: float = 0.0
                          ) -> dict:
        """Would the earlier ACP evaluation still be valid at commit? (§7, no gate)."""
        if self._last is None:
            return {"revalidated": False, "reason": "no prior evaluation"}
        try:
            if candidate.identity != self._last["candidate"].identity:
                raise AuthorizationBindingError("trajectory/candidate identity changed")
            if current_world_state.version != self._last["world_version"]:
                raise StaleAuthorizationError("world-state identity changed")
            if (now_s - evidence_time_s) > max_stale_s:
                raise StaleAuthorizationError("physical evidence no longer fresh")
            return {"revalidated": True, "reason": "ok"}
        except (AuthorizationBindingError, StaleAuthorizationError) as e:
            return {"revalidated": False, "reason": type(e).__name__ + ": " + str(e)}


class InstrumentedTaskPlanner:
    """Composes a real planner; returns its plan unchanged; fires the hook."""

    def __init__(self, real_planner, hook: ShadowPlannerHook):
        self._planner = real_planner
        self._hook = hook

    def plan(self, *args, shadow_context: Optional[dict] = None, **kwargs):
        # The authoritative call — unchanged behaviour, unchanged exceptions.
        plan = self._planner.plan(*args, **kwargs)
        # Out-of-band shadow (contained). Requires context to bind the world
        # state + initial joints; if absent, the hook is simply not fired.
        if self._hook.enabled and shadow_context is not None:
            self._hook.observe(plan=plan, **shadow_context)
        return plan

    def __getattr__(self, name):
        return getattr(self._planner, name)
