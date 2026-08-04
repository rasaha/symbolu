"""Execution-mode semantics."""

from __future__ import annotations

from ugence_cloud_scaling_operations import (
    ControlledScalingExecutor, OperationsConfig, TargetPolicy, ExecutionMode,
    FakeScalingBackend,
)
import ops_support as support


def _tp():
    return TargetPolicy(allowed_clusters=("prod-a",), allowed_namespaces=("web",),
                        allowed_resources=("frontend",), max_replica_delta=5,
                        min_replicas=1, max_replicas=10)


def test_dry_run_performs_no_mutation():
    backend = FakeScalingBackend({"prod-a/web/frontend": 3})
    ex = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.DRY_RUN),
                                   backend=backend, clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), tenant_id="tenant-1")
    assert r.outcome == "proposed" and r.applied is False
    assert backend.read_replicas("prod-a", "web", "frontend") == 3  # unchanged


def test_simulation_no_external_mutation():
    backend = FakeScalingBackend({"prod-a/web/frontend": 3})
    ex = ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.SIMULATION, target_policy=_tp()),
        backend=backend, verifier=support.verifier(), clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "simulated" and r.applied is False


def test_shadow_is_read_only():
    backend = FakeScalingBackend({"prod-a/web/frontend": 4})
    ex = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.SHADOW),
                                   backend=backend, clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), tenant_id="tenant-1")
    assert r.outcome == "shadowed" and r.applied is False
    assert backend.read_replicas("prod-a", "web", "frontend") == 4


def test_live_refuses_missing_backend():
    ex = ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.LIVE, target_policy=_tp()),
        backend=None, verifier=support.verifier(), clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "denied" and "backend" in (r.denial_reason or "")


def test_live_refuses_insecure_tls():
    ex = ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.LIVE, target_policy=_tp(), allow_insecure_tls=True),
        backend=FakeScalingBackend({"prod-a/web/frontend": 3}),
        verifier=support.verifier(), clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "denied" and "TLS" in (r.denial_reason or "")


def test_live_refuses_failed_readiness():
    from ugence_cloud_scaling_operations import ReadinessEvaluator
    ex = ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.LIVE, target_policy=_tp()),
        backend=FakeScalingBackend({"prod-a/web/frontend": 3}),
        verifier=support.verifier(), readiness=ReadinessEvaluator(check=lambda req: False),
        clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "denied" and "readiness" in (r.denial_reason or "")


def test_live_requires_authorization():
    ex = ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.LIVE, target_policy=_tp()),
        backend=FakeScalingBackend({"prod-a/web/frontend": 3}),
        verifier=support.verifier(), clock=lambda: 1500.0)
    r = ex.execute(support.make_request(), None, tenant_id="tenant-1")
    assert r.outcome == "denied"
