"""The genuine chain, extended by a grant: 5X's world plus a materialized grant, an executor
built over the deterministic fake backend, and the seam. Nothing here adds authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Optional

from ugence_cloud_scaling_operations.config import OperationsConfig, TargetPolicy
from ugence_cloud_scaling_operations.contracts import ExecutionMode
from ugence_cloud_scaling_operations.executors import FakeScalingBackend, InMemoryAuditSink, ReadinessEvaluator
from ugence_cloud_scaling_operations.idempotency import InMemoryIdempotencyStore

from _broker_fixtures import BROKER_INSTANT, build_broker_world, materialization_request, production_app

from ugence_cloud_scaling_bounded_execution import (
    BoundedDispatch,
    BoundedExecutionSeam,
    ExecutorParts,
    InMemoryBoundedExecutionRecordStore,
    ops_target_for,
)
from ugence_cloud_scaling_credential_broker import InMemoryCredentialGrantStore

__all__ = ["DISPATCH_INSTANT", "DISPATCH_REQUEST_ID", "World", "build_execution_world", "dispatch_request",
           "simulation_config", "production_app", "fake_backend_for"]

DISPATCH_INSTANT: datetime = BROKER_INSTANT + timedelta(seconds=2)
DISPATCH_REQUEST_ID = "dispatch-5d-1"


def simulation_config(mode: ExecutionMode = ExecutionMode.SIMULATION, **policy) -> OperationsConfig:
    """A permissive deployment config: wide ceilings the seam must narrow to the role."""

    kw = dict(allowed_clusters=(), allowed_namespaces=(), allowed_resources=(),
              max_replica_delta=50, min_replicas=0, max_replicas=1000)
    kw.update(policy)
    tp = TargetPolicy(**kw)
    return OperationsConfig(mode=mode, target_policy=tp, require_audit_sink=True, require_readiness=True)


def fake_backend_for(target_scope) -> FakeScalingBackend:
    target = ops_target_for(target_scope)
    return FakeScalingBackend({f"{target.cluster}/{target.namespace}/{target.resource}": target_scope.magnitude_before})


@dataclass
class World:
    clock: Any
    app: Any
    candidate: Any
    envelope: Any
    authorization: Any
    action: Any
    reservations: Any
    reservation: Any
    grants: InMemoryCredentialGrantStore
    grant: Any
    broker_world: Any
    records: InMemoryBoundedExecutionRecordStore
    audit: InMemoryAuditSink
    idempotency: InMemoryIdempotencyStore

    @property
    def target_scope(self):
        return self.candidate.target_scope

    def parts(self, config: Optional[OperationsConfig] = None, *, backend="fake", readiness=None) -> ExecutorParts:
        return ExecutorParts(config=config or simulation_config(),
                             backend=fake_backend_for(self.target_scope) if backend == "fake" else backend,
                             audit_sink=self.audit, idempotency_store=self.idempotency,
                             readiness=readiness or ReadinessEvaluator())

    def seam(self, config: Optional[OperationsConfig] = None, **overrides) -> BoundedExecutionSeam:
        kw = dict(app=self.app, reservations=self.reservations, grants=self.grants, records=self.records,
                  parts=self.parts(config), clock=self.clock)
        kw.update(overrides)
        return BoundedExecutionSeam.reference(**kw)


def build_execution_world() -> World:
    bw = build_broker_world()
    grants = InMemoryCredentialGrantStore()
    out = bw.seam(grants=grants).materialize(materialization_request(bw))
    assert out.materialized, (out.refusal, out.detail)
    clock = bw.clock
    clock.at = DISPATCH_INSTANT
    clock.reads = 0
    return World(clock=clock, app=bw.app, candidate=bw.candidate, envelope=bw.envelope,
                 authorization=bw.authorization, action=bw.action, reservations=bw.reservations,
                 reservation=bw.reservation, grants=grants, grant=out.grant, broker_world=bw,
                 records=InMemoryBoundedExecutionRecordStore(), audit=InMemoryAuditSink(),
                 idempotency=InMemoryIdempotencyStore())


def dispatch_request(world: World, **overrides) -> BoundedDispatch:
    base = dict(tenant_id=world.candidate.tenant_id, grant_id=world.grant.grant_id,
                reservation_id=world.reservation.reservation_id,
                authorization_id=world.authorization.authorization_id, target_scope=world.target_scope,
                dispatch_request_id=DISPATCH_REQUEST_ID)
    base.update(overrides)
    return BoundedDispatch(**base)
