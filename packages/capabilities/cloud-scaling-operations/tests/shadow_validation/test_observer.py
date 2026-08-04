"""Observer routes reads through the barrier and never auto-discovers credentials."""
from __future__ import annotations

import pytest

from shadow_validation.config import ShadowValidationConfig
from shadow_validation.observer import (
    RealEnvironmentAdapter, refuse_auto_discovery, ObservationError, RetryPolicy,
    bounded_read, FakeReadOnlyKubernetesClient,
)
from shadow_validation.allowlist import TargetRef
from shadow_validation.session import build_fixture_observer, default_fixture_targets
from shadow_validation.transport import ReadOnlyTransportBarrier, Destination


def test_observer_reads_route_through_barrier_as_read_verbs():
    cfg = ShadowValidationConfig.fixture()
    targets = default_fixture_targets()
    observer, barrier = build_fixture_observer(cfg, targets)
    ref = TargetRef(cfg.cluster_identifier, "shadow-test", "Deployment", "frontend")
    dep = observer.observe_deployment(ref)
    assert dep.current_replicas == 3
    methods = {e.method for e in barrier.ledger.entries}
    assert methods.issubset({"GET", "LIST", "WATCH", "HEAD"})
    assert barrier.ledger.transmitted_write_methods() == []


def test_observer_refuses_non_allowlisted_target():
    cfg = ShadowValidationConfig.fixture()
    observer, _ = build_fixture_observer(cfg, default_fixture_targets())
    with pytest.raises(PermissionError):
        observer.observe_deployment(TargetRef(cfg.cluster_identifier, "kube-system",
                                              "Deployment", "frontend"))


def test_refuse_auto_discovery_raises():
    with pytest.raises(RuntimeError):
        refuse_auto_discovery()


def test_real_adapter_requires_explicit_client_and_config():
    with pytest.raises(ValueError):
        RealEnvironmentAdapter(None, explicit_config=object())
    with pytest.raises(ValueError):
        RealEnvironmentAdapter(object(), explicit_config=None)


def test_bounded_read_contains_failures_without_mutation():
    barrier = ReadOnlyTransportBarrier(clock=lambda: 1000.0)

    def fault(op, ns, nm):
        raise TimeoutError("timeout")

    client = FakeReadOnlyKubernetesClient(barrier, cluster="fake-cluster",
                                          deployments={"shadow-test/frontend": None},
                                          fault=fault)
    with pytest.raises(ObservationError):
        bounded_read(lambda: client.read_deployment("shadow-test", "frontend"),
                     RetryPolicy(max_attempts=3))
    assert barrier.ledger.transmitted_write_methods() == []
