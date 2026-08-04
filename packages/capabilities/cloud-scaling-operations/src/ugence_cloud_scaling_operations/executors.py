"""Controlled executors: authority-gated infrastructure mutation.

The :class:`ControlledScalingExecutor` is the only supported production mutation path.
It fails closed without a valid :class:`ExecutionAuthorization`, enforces target
allowlists / bounds / staleness / idempotency / readiness / audit, and only mutates in
LIVE mode. Backends are injected (duck-typed); deterministic fakes drive SIMULATION and
tests. No credentials are read and no SDK is imported at module import time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable

from .audit import AuditEvent, AuditSink, AuditSinkError, InMemoryAuditSink
from .authority import AuthorityVerifier, ReferenceAuthorityVerifier, verify_authorization
from .config import OperationsConfig
from .contracts import (
    ExecutionAction,
    ExecutionAuthorization,
    ExecutionDenied,
    ExecutionIntegrityError,
    ExecutionMode,
    ExecutionOutcome,
    ExecutionReceipt,
    ExecutionRequest,
    SCHEMA_VERSION,
)
from .idempotency import IdempotencyRecord, IdempotencyStore, InMemoryIdempotencyStore
from .version import __version__


class ConcurrencyConflict(Exception):
    """Optimistic-concurrency conflict: observed pre-state != expected."""


@runtime_checkable
class ScalingBackend(Protocol):
    """Injected mutation backend. Real implementations live behind optional extras."""

    def read_replicas(self, cluster: str, namespace: str, resource: str) -> int:
        ...

    def set_replicas(self, cluster: str, namespace: str, resource: str,
                     target: int, expected_current: int) -> Dict:
        ...


class FakeScalingBackend:
    """Deterministic in-memory backend for SIMULATION and tests. No network."""

    def __init__(self, state: Optional[Dict] = None, *, fail_on: Optional[str] = None,
                 conflict_on: Optional[str] = None):
        self._state: Dict = dict(state or {})
        self._fail_on = fail_on          # resource name that raises a backend error
        self._conflict_on = conflict_on  # resource name that raises ConcurrencyConflict

    def _key(self, c, n, r):
        return f"{c}/{n}/{r}"

    def read_replicas(self, cluster, namespace, resource) -> int:
        return int(self._state.get(self._key(cluster, namespace, resource), 0))

    def set_replicas(self, cluster, namespace, resource, target, expected_current) -> Dict:
        if resource == self._fail_on:
            raise RuntimeError("simulated backend error")
        key = self._key(cluster, namespace, resource)
        actual = int(self._state.get(key, expected_current))
        if resource == self._conflict_on or actual != expected_current:
            raise ConcurrencyConflict(
                f"expected {expected_current} but observed {actual}")
        self._state[key] = int(target)
        return {"observedGeneration": 1, "replicas": int(target)}


@dataclass
class ReadinessEvaluator:
    """Readiness gate. In LIVE a real check callable must be supplied."""

    check: Optional[Callable[[ExecutionRequest], bool]] = None

    def is_ready(self, request: ExecutionRequest) -> bool:
        if self.check is None:
            return True
        return bool(self.check(request))


class OutcomeRecorder:
    """Records execution receipts (in addition to the audit sink)."""

    def __init__(self):
        self.receipts: List[ExecutionReceipt] = []

    def record(self, receipt: ExecutionReceipt) -> None:
        self.receipts.append(receipt)


class ControlledScalingExecutor:
    """Authority-gated scaling executor.

    ``execute`` never mutates real infrastructure outside LIVE mode; LIVE additionally
    requires a valid authorization, a backend, an audit sink, readiness, and secure TLS.
    """

    _APPLYING_MODES = (ExecutionMode.SIMULATION, ExecutionMode.LIVE)

    def __init__(
        self,
        config: Optional[OperationsConfig] = None,
        *,
        backend: Optional[ScalingBackend] = None,
        verifier: Optional[AuthorityVerifier] = None,
        idempotency_store: Optional[IdempotencyStore] = None,
        audit_sink: Optional[AuditSink] = None,
        readiness: Optional[ReadinessEvaluator] = None,
        outcome_recorder: Optional[OutcomeRecorder] = None,
        clock: Optional[Callable[[], float]] = None,
        source_revision: Optional[str] = None,
    ):
        self.config = config or OperationsConfig()
        self.backend = backend
        self.verifier = verifier or ReferenceAuthorityVerifier(require_signature=False)
        self.idempotency = idempotency_store or InMemoryIdempotencyStore()
        self.audit = audit_sink or InMemoryAuditSink()
        self.readiness = readiness or ReadinessEvaluator()
        self.outcomes = outcome_recorder or OutcomeRecorder()
        self._source_revision = source_revision
        if clock is None:
            import time as _t
            clock = _t.time
        self._clock = clock

    # ------------------------------------------------------------------ helpers
    def _target_str(self, req: ExecutionRequest) -> str:
        return f"{req.target_cluster}/{req.target_namespace}/{req.target_resource}"

    def _emit(self, req, authz, outcome, pre, post, denial, retry, tenant, actor):
        ev = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=self._clock(),
            tenant_id=tenant,
            actor_id=actor,
            authorization_id=(authz.authorization_id if authz else None),
            decision_id=(authz.decision_id if authz else None),
            recommendation_id=req.recommendation_id,
            target=self._target_str(req),
            requested_action=req.action,
            authorized_bounds=(f"[{authz.minimum_replicas},{authz.maximum_replicas}]"
                               f" delta<= {authz.maximum_delta}" if authz else None),
            execution_mode=self.config.mode.value,
            pre_state=pre,
            post_state=post,
            result=outcome.value,
            denial_reason=denial,
            retry_count=retry,
            rollback_reference=None,
            package_version=__version__,
            source_revision=self._source_revision,
        )
        try:
            self.audit.emit(ev)
        except Exception as exc:  # pragma: no cover
            if self.config.is_live():
                raise AuditSinkError(str(exc))
        return ev.event_id

    def _receipt(self, req, authz, outcome, pre, post, applied, denial, detail, audit_id):
        return ExecutionReceipt(
            schema_version=SCHEMA_VERSION,
            outcome=outcome.value,
            action=req.action,
            execution_mode=self.config.mode.value,
            target_cluster=req.target_cluster,
            target_namespace=req.target_namespace,
            target_resource=req.target_resource,
            pre_state=pre,
            post_state=post,
            requested_replicas=req.target_replicas,
            applied=applied,
            authorization_id=(authz.authorization_id if authz else None),
            recommendation_id=req.recommendation_id,
            correlation_id=req.correlation_id,
            idempotency_key=req.idempotency_key,
            denial_reason=denial,
            detail=detail,
            audit_event_id=audit_id,
            timestamp=self._clock(),
        )

    # ------------------------------------------------------------------ public
    def execute(
        self,
        request: ExecutionRequest,
        authorization: Optional[ExecutionAuthorization] = None,
        *,
        tenant_id: str = "",
        actor_id: str = "system",
    ) -> ExecutionReceipt:
        now = self._clock()
        mode = self.config.mode

        # DRY_RUN: propose only, no authority needed, no backend call.
        if mode == ExecutionMode.DRY_RUN:
            audit_id = self._emit(request, authorization, ExecutionOutcome.PROPOSED,
                                  request.current_replicas, request.target_replicas,
                                  None, 0, tenant_id, actor_id)
            r = self._receipt(request, authorization, ExecutionOutcome.PROPOSED,
                              request.current_replicas, request.target_replicas,
                              False, None, "dry-run: no mutation performed", audit_id)
            self.outcomes.record(r)
            return r

        # SHADOW: read-only observation, never mutate, no authority needed.
        if mode == ExecutionMode.SHADOW:
            pre = self.backend.read_replicas(request.target_cluster, request.target_namespace,
                                             request.target_resource) if self.backend else None
            audit_id = self._emit(request, authorization, ExecutionOutcome.SHADOWED,
                                  pre, pre, None, 0, tenant_id, actor_id)
            r = self._receipt(request, authorization, ExecutionOutcome.SHADOWED, pre, pre,
                              False, None, "shadow: read-only observation", audit_id)
            self.outcomes.record(r)
            return r

        # Applying modes (SIMULATION, LIVE) require authority — fail closed.
        try:
            verify_authorization(authorization, request, self.config, self.verifier,
                                 now=now, tenant_id=tenant_id)
        except ExecutionDenied as denied:
            audit_id = self._emit(request, authorization, ExecutionOutcome.DENIED,
                                  request.current_replicas, None, denied.reason, 0,
                                  tenant_id, actor_id)
            r = self._receipt(request, authorization, ExecutionOutcome.DENIED,
                              request.current_replicas, None, False, denied.reason,
                              f"denied: {denied.code}", audit_id)
            self.outcomes.record(r)
            return r

        # Idempotency / replay protection.
        prior = self.idempotency.get(request.idempotency_key)
        if prior is not None:
            if (prior.request_digest != request.digest()
                    or prior.authorization_id != authorization.authorization_id):
                raise ExecutionIntegrityError(
                    "idempotency key reused with a different request/authorization")
            if prior.completed:
                audit_id = self._emit(request, authorization, ExecutionOutcome.DUPLICATE,
                                      request.current_replicas, request.target_replicas,
                                      None, 0, tenant_id, actor_id)
                r = self._receipt(request, authorization, ExecutionOutcome.DUPLICATE,
                                  request.current_replicas, request.target_replicas, False,
                                  None, "duplicate: prior completed execution", audit_id)
                self.outcomes.record(r)
                return r

        # LIVE preconditions.
        if mode == ExecutionMode.LIVE:
            denial = self._live_precondition_denial(request)
            if denial:
                audit_id = self._emit(request, authorization, ExecutionOutcome.DENIED,
                                      request.current_replicas, None, denial, 0,
                                      tenant_id, actor_id)
                r = self._receipt(request, authorization, ExecutionOutcome.DENIED,
                                  request.current_replicas, None, False, denial,
                                  "denied: live_precondition", audit_id)
                self.outcomes.record(r)
                return r

        # Apply (SIMULATION against fake, LIVE against real injected backend).
        backend = self.backend or FakeScalingBackend(
            {f"{request.target_cluster}/{request.target_namespace}/{request.target_resource}":
             request.current_replicas})
        outcome = (ExecutionOutcome.SIMULATED if mode == ExecutionMode.SIMULATION
                   else ExecutionOutcome.APPLIED)
        try:
            pre = backend.read_replicas(request.target_cluster, request.target_namespace,
                                        request.target_resource)
            resp = backend.set_replicas(request.target_cluster, request.target_namespace,
                                        request.target_resource, request.target_replicas,
                                        request.current_replicas)
            post = int(resp.get("replicas", request.target_replicas))
            applied = (mode == ExecutionMode.LIVE)
            audit_id = self._emit(request, authorization, outcome, pre, post, None, 0,
                                  tenant_id, actor_id)
            r = self._receipt(request, authorization, outcome, pre, post, applied, None,
                              "ok", audit_id)
        except ConcurrencyConflict as exc:
            audit_id = self._emit(request, authorization, ExecutionOutcome.FAILED,
                                  request.current_replicas, None, str(exc), 0,
                                  tenant_id, actor_id)
            r = self._receipt(request, authorization, ExecutionOutcome.FAILED,
                              request.current_replicas, None, False, str(exc),
                              "concurrency_conflict", audit_id)
            self.outcomes.record(r)
            return r
        except Exception as exc:  # backend error
            audit_id = self._emit(request, authorization, ExecutionOutcome.FAILED,
                                  request.current_replicas, None, str(exc), 0,
                                  tenant_id, actor_id)
            r = self._receipt(request, authorization, ExecutionOutcome.FAILED,
                              request.current_replicas, None, False, str(exc),
                              "backend_error", audit_id)
            self.outcomes.record(r)
            return r

        # Record idempotency completion.
        self.idempotency.put(IdempotencyRecord(
            idempotency_key=request.idempotency_key,
            authorization_id=authorization.authorization_id,
            target=self._target_str(request),
            action=request.action,
            request_digest=request.digest(),
            completed=True,
            receipt_hash=r.receipt_hash(),
            first_seen=now,
        ))
        self.outcomes.record(r)
        return r

    def _live_precondition_denial(self, request: ExecutionRequest) -> Optional[str]:
        if self.backend is None:
            return "LIVE requires an injected scaling backend"
        if self.config.require_audit_sink and self.audit is None:
            return "LIVE requires an audit sink"
        if self.config.allow_insecure_tls:
            return "insecure TLS is forbidden in LIVE mode"
        if self.config.require_readiness and not self.readiness.is_ready(request):
            return "readiness check failed"
        return None


__all__ = [
    "ControlledScalingExecutor",
    "ScalingBackend",
    "FakeScalingBackend",
    "ConcurrencyConflict",
    "ReadinessEvaluator",
    "OutcomeRecorder",
]
