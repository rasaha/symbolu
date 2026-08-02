"""The deterministic Action Clearance evaluator (design §17–22).

``ActionClearanceEvaluator.evaluate`` (and the ``evaluate_clearance`` helper) is a
pure function of the request: no clock read, no randomness, no network, no
persistence, no dispatch. It preserves/narrows/holds/escalates/blocks an existing
authorization and never creates authority or broadens it.

Signal value conventions (neutral, documented): each signal's normalized ``value``
is read per ``signal_type`` — a mapping with a small set of canonical keys, or a
scalar. See ``docs/TRUSTED_SIGNALS.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

from ..errors import ValidationError
from ..fingerprinting import DOMAIN_ACTION  # noqa: F401 (kept for reference)
from ..models.constraints import (
    ConstraintOutcome,
    EffectiveConstraint,
    intersect,
)
from ..models.enums import (
    ELIGIBLE_OUTCOMES,
    ClearanceStatus,
    ConsumptionStatus,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    combine_statuses,
    trust_at_least,
)
from ..models.request import ClearanceRequest
from ..models.result import ClearanceResult
from ..models.signals import TrustedSignal
from ..normalization import normalize_value
from ..policy import ClearancePolicy
from ..reason_codes import (
    ClearanceReasonCode as RC,
    canonical_reason_order,
    default_status,
)

# Signal types that must bind to the exact action (vs environment-global ones).
_ACTION_SCOPED = frozenset({
    SignalType.ARTIFACT_IDENTITY, SignalType.REQUIRED_CONTROL,
    SignalType.TARGET_AVAILABILITY, SignalType.PRIOR_CONSUMPTION,
    SignalType.AUTHORIZATION_VALIDITY, SignalType.POLICY_VALIDITY,
    SignalType.ACTOR_STATUS,
})
_TIME_BOUNDED = frozenset({
    SignalType.AUTHORIZATION_VALIDITY, SignalType.ARTIFACT_IDENTITY,
    SignalType.ACTOR_STATUS, SignalType.POLICY_VALIDITY,
    SignalType.REQUIRED_CONTROL, SignalType.PRIOR_CONSUMPTION,
})


@dataclass
class _Contribution:
    reason: RC
    status: ClearanceStatus


class _Acc:
    def __init__(self) -> None:
        self._items: List[_Contribution] = []

    def add(self, reason: RC, status: Optional[ClearanceStatus] = None) -> None:
        self._items.append(_Contribution(reason, status or default_status(reason)))

    @property
    def reasons(self) -> Tuple[RC, ...]:
        return tuple(c.reason for c in self._items)

    @property
    def statuses(self) -> Tuple[ClearanceStatus, ...]:
        return tuple(c.status for c in self._items)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return default


class ActionClearanceEvaluator:
    """Stateless deterministic clearance evaluator."""

    def evaluate(self, request: ClearanceRequest, policy: ClearancePolicy) -> ClearanceResult:
        self._validate(request)
        acc = _Acc()
        et = request.evaluation_time
        auth = request.authorization
        action = request.action

        # --- authorization eligibility + expiry -------------------------
        if auth.authorization_outcome not in ELIGIBLE_OUTCOMES:
            acc.add(RC.AUTHORIZATION_NOT_ELIGIBLE)
            acc.add(RC.UPSTREAM_REAUTHORIZATION_REQUIRED)
        if et >= auth.authorization_expires_at:  # inclusive-expiry = expired
            acc.add(RC.AUTHORIZATION_EXPIRED)
            acc.add(RC.UPSTREAM_REAUTHORIZATION_REQUIRED)

        # --- per-signal structural + freshness + trust + semantics ------
        present_by_type: dict = {}
        for s in request.signals.signals:
            self._eval_signal(s, request, policy, acc, present_by_type)

        # --- required signals present? ----------------------------------
        for req_type in policy.required_signal_types:
            live = present_by_type.get(req_type, [])
            if not live:
                acc.add(RC.SIGNAL_MISSING)

        # --- conflict detection (same type, disagreeing values) ---------
        for stype, sigs in present_by_type.items():
            distinct = {_content_key(s) for s in sigs}
            if len(distinct) > 1:
                acc.add(RC.SIGNAL_CONFLICT)

        # --- constraint intersection (narrowing only) -------------------
        effective_constraints = self._intersect_constraints(request, policy, acc)

        # --- obligations (superset; never remove upstream) --------------
        obligations = tuple(sorted(set(auth.authorization_obligations) | set(policy.added_obligations)))

        # --- status + validity window -----------------------------------
        status = combine_statuses(acc.statuses) if acc.statuses else ClearanceStatus.CLEAR
        reasons = list(acc.reasons)
        if status is ClearanceStatus.CLEAR:
            reasons = [RC.CLEARANCE_GRANTED]
        valid_until = self._valid_until(request, policy, present_by_type)

        ordered = canonical_reason_order(reasons)
        signal_refs = tuple(sorted(s.signal_id for s in request.signals.signals))

        return ClearanceResult(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            authorization_ref=auth.authorization_ref,
            authorized_action_fingerprint=action.authorized_action_fingerprint,
            status=status,
            reason_codes=tuple(c.value for c in ordered),
            effective_constraints=effective_constraints,
            obligations=obligations,
            evaluated_at=et,
            valid_until=valid_until,
            policy_refs=tuple(sorted(set(request.policy.policy_refs) | {policy.policy_ref})),
            signal_refs=signal_refs,
            request_fingerprint=request.fingerprint,
            signal_bundle_fingerprint=request.signals.fingerprint,
        )

    # --- validation ------------------------------------------------------
    def _validate(self, request: ClearanceRequest) -> None:
        et = request.evaluation_time
        skew = request.policy.clock_skew_tolerance_s or 0
        for s in request.signals.signals:
            # future capture beyond skew tolerance is malformed (not an outcome)
            if s.captured_at > et + timedelta(seconds=skew):
                raise ValidationError(
                    f"signal {s.signal_id} captured_at is in the future beyond skew tolerance")
        # prohibited payloads: credentials/executable commands are never accepted
        for s in request.signals.signals:
            if isinstance(s.value, dict):
                for banned in ("credential", "credentials", "secret", "token", "password",
                               "provider_command", "exec"):
                    if banned in s.value:
                        raise ValidationError(f"prohibited key {banned!r} in signal value")

    # --- per-signal evaluation ------------------------------------------
    def _eval_signal(self, s: TrustedSignal, request: ClearanceRequest,
                     policy: ClearancePolicy, acc: _Acc, present_by_type: dict) -> None:
        # tenant binding
        if s.tenant_id != request.tenant_id:
            acc.add(RC.TENANT_MISMATCH)
            return
        # subject / authorization / action binding
        if s.signal_type in _ACTION_SCOPED and not self._subject_bound(s, request):
            acc.add(RC.SUBJECT_MISMATCH)
            return
        if s.authorization_ref and s.authorization_ref != request.authorization.authorization_ref:
            acc.add(RC.SIGNAL_AUTHORIZATION_MISMATCH)
            return
        if s.action_fingerprint and s.action_fingerprint != request.action.authorized_action_fingerprint:
            acc.add(RC.SIGNAL_ACTION_MISMATCH)
            return
        # liveness
        if s.status is SignalStatus.UNKNOWN:
            acc.add(RC.SIGNAL_MISSING)  # required source unavailable → fail closed
            return
        if s.status is SignalStatus.ABSENT:
            return  # a declared-absent signal contributes nothing here; presence handled elsewhere
        # trust / provenance (policy-gated)
        if not self._trust_ok(s, policy, acc):
            return
        # freshness
        if not self._freshness_ok(s, request, policy, acc):
            # staleness recorded; still record presence for conflict/missing accounting
            present_by_type.setdefault(s.signal_type, []).append(s)
            return
        present_by_type.setdefault(s.signal_type, []).append(s)
        # type-specific semantics
        self._semantics(s, request, policy, acc)

    def _subject_bound(self, s: TrustedSignal, request: ClearanceRequest) -> bool:
        a = request.action
        bindings = {a.target_ref, a.artifact_ref, a.actor_ref,
                    a.authorized_action_fingerprint, request.authorization.authorization_ref}
        return s.subject_ref in {b for b in bindings if b}

    def _trust_ok(self, s: TrustedSignal, policy: ClearancePolicy, acc: _Acc) -> bool:
        needs_trust = s.signal_type in policy.trust_required_signal_types
        # content integrity: a supplied integrity_digest must match the content fingerprint
        if s.integrity_digest is not None and s.integrity_digest != s.content_fingerprint:
            acc.add(RC.SIGNAL_CONTENT_MISMATCH)
            return False
        if not needs_trust:
            return True
        if s.provenance is None:
            acc.add(RC.SIGNAL_PROVENANCE_MISSING)
            return False
        if s.integrity_digest is None:
            acc.add(RC.SIGNAL_UNTRUSTED)
            return False
        prov = s.provenance
        approved_kinds = policy.approved_source_kinds.get(s.signal_type.value)
        if approved_kinds is not None and prov.source_kind not in approved_kinds:
            acc.add(RC.SIGNAL_SOURCE_UNAPPROVED)
            return False
        if prov.adapter_id is not None:
            approved_versions = policy.approved_adapter_versions.get(prov.adapter_id)
            if approved_versions is not None and prov.adapter_version not in approved_versions:
                acc.add(RC.SIGNAL_ADAPTER_VERSION_UNAPPROVED)
                return False
        min_trust = policy.min_trust_for(s.signal_type)
        if min_trust is not None and not trust_at_least(prov.trust_level, min_trust):
            acc.add(RC.SIGNAL_TRUST_LEVEL_INSUFFICIENT)
            return False
        return True

    def _freshness_ok(self, s: TrustedSignal, request: ClearanceRequest,
                      policy: ClearancePolicy, acc: _Acc) -> bool:
        et = request.evaluation_time
        if s.signal_type in _TIME_BOUNDED:
            if s.valid_until is None:
                acc.add(RC.SIGNAL_STALE)  # missing bound on time-bounded signal → fail closed
                return False
            if et >= s.valid_until:  # inclusive-expiry
                acc.add(RC.SIGNAL_EXPIRED)
                return False
        if policy.maximum_signal_age_s is not None:
            if (et - s.captured_at) > timedelta(seconds=policy.maximum_signal_age_s):
                acc.add(RC.SIGNAL_STALE)
                return False
        return True

    def _semantics(self, s: TrustedSignal, request: ClearanceRequest,
                   policy: ClearancePolicy, acc: _Acc) -> None:
        t = s.signal_type
        v = s.value
        if t is SignalType.ACTOR_STATUS:
            state = _get(v, "state", v)
            if state == "DISABLED":
                acc.add(RC.ACTOR_INVALID)
            elif state in ("UNKNOWN", None):
                acc.add(RC.ACTOR_STATUS_UNKNOWN)
        elif t is SignalType.CHANGE_FREEZE:
            if _get(v, "active", False):
                acc.add(RC.ACTIVE_CHANGE_FREEZE)
        elif t is SignalType.ACTIVE_INCIDENT:
            if _get(v, "active", False):
                acc.add(RC.ACTIVE_INCIDENT, policy.incident_response)
        elif t is SignalType.ARTIFACT_IDENTITY:
            current_fp = _get(v, "action_fingerprint", v)
            if current_fp != request.action.authorized_action_fingerprint:
                acc.add(RC.ACTION_FINGERPRINT_MISMATCH)
            current_target = _get(v, "target_ref", None)
            if current_target is not None and current_target != request.action.target_ref:
                acc.add(RC.TARGET_MISMATCH)
        elif t is SignalType.REQUIRED_CONTROL:
            if not _get(v, "satisfied", False):
                acc.add(RC.REQUIRED_CONTROL_UNSATISFIED)
        elif t is SignalType.TARGET_AVAILABILITY:
            if not _get(v, "available", False):
                acc.add(RC.TARGET_UNAVAILABLE)
        elif t is SignalType.PRIOR_CONSUMPTION:
            state = _get(v, "state", v)
            if state == ConsumptionStatus.CONSUMED.value:
                acc.add(RC.ALREADY_CONSUMED)
            elif state == ConsumptionStatus.RESERVED.value:
                acc.add(RC.CONSUMPTION_RESERVED, policy.consumption_reserved_response)
            elif state in (ConsumptionStatus.UNKNOWN.value, None):
                acc.add(RC.CONSUMPTION_STATUS_UNKNOWN)
        elif t is SignalType.POLICY_VALIDITY:
            if not _get(v, "accepted", True):
                acc.add(RC.POLICY_VERSION_REJECTED)
        elif t is SignalType.AUTHORIZATION_VALIDITY:
            state = _get(v, "state", v)
            if state in ("INVALID", "STALE"):
                acc.add(RC.AUTHORIZATION_STALE)

    # --- constraints -----------------------------------------------------
    def _intersect_constraints(self, request: ClearanceRequest, policy: ClearancePolicy,
                               acc: _Acc) -> Tuple[str, ...]:
        auth = request.authorization
        effective: List[str] = list(auth.authorization_constraints)  # opaque, always preserved
        auth_structured = {c.dimension: c for c in auth.structured_constraints}
        for c in auth.structured_constraints:
            effective.append(c.canonical())
        for cc in policy.clearance_constraints:
            match = auth_structured.get(cc.dimension)
            if match is None:
                # pure narrowing addition on a new dimension
                effective.append(cc.canonical())
                continue
            res = intersect(match, cc)
            if res.outcome is ConstraintOutcome.CONFLICT:
                acc.add(RC.CONSTRAINT_CONFLICT, policy.constraint_conflict_response)
            elif res.outcome is ConstraintOutcome.UNSUPPORTED:
                acc.add(RC.CONSTRAINT_INTERPRETATION_UNSUPPORTED)
            elif res.constraint is not None:
                effective.append(res.constraint.canonical())
        return tuple(sorted(set(effective)))

    # --- validity window -------------------------------------------------
    def _valid_until(self, request: ClearanceRequest, policy: ClearancePolicy,
                     present_by_type: dict) -> datetime:
        et = request.evaluation_time
        bounds = [request.authorization.authorization_expires_at]
        for req_type in policy.required_signal_types:
            for s in present_by_type.get(req_type, []):
                if s.valid_until is not None:
                    bounds.append(s.valid_until)
        lifetime = policy.maximum_clearance_lifetime_s or request.policy.max_clearance_lifetime_s
        if lifetime is not None:
            bounds.append(et + timedelta(seconds=lifetime))
        return min(bounds)


def evaluate_clearance(request: ClearanceRequest, policy: ClearancePolicy) -> ClearanceResult:
    """Module-level convenience wrapper around :class:`ActionClearanceEvaluator`."""
    return ActionClearanceEvaluator().evaluate(request, policy)


def _content_key(s: TrustedSignal) -> str:
    return s.content_fingerprint


__all__ = ["ActionClearanceEvaluator", "evaluate_clearance"]
