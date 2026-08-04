"""Execution tests using fakes only — Kubernetes, ArgoCD, rollback, idempotency."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_operations import (
    ControlledScalingExecutor, OperationsConfig, TargetPolicy, ExecutionMode,
    FakeScalingBackend, ConcurrencyConflict, KubernetesScalingExecutor, GateExecutor,
    RollbackCoordinator, RollbackPlan, RollbackAuthorization, RollbackPolicy,
    ExecutionRequest,
)
import support


def _tp():
    return TargetPolicy(allowed_clusters=("prod-a",), allowed_namespaces=("web",),
                        allowed_resources=("frontend",), max_replica_delta=5,
                        min_replicas=1, max_replicas=10)


def _live(backend, **over):
    return ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.LIVE, target_policy=_tp()),
        backend=backend, verifier=support.verifier(), clock=lambda: 1500.0, **over)


# ---- Kubernetes (fake AppsV1Api client) ----

class _Scale:
    def __init__(self, replicas, rv="1"):
        self.spec = type("S", (), {"replicas": replicas})()
        self.metadata = type("M", (), {"resource_version": rv})()


class FakeAppsV1:
    def __init__(self, replicas=3, conflict=False, error=False):
        self._replicas = replicas
        self._conflict = conflict
        self._error = error
        self.patched = None

    def read_namespaced_deployment_scale(self, name, namespace):
        return _Scale(self._replicas)

    def patch_namespaced_deployment_scale(self, name, namespace, body):
        if self._error:
            raise RuntimeError("k8s api error")
        self.patched = body["spec"]["replicas"]
        return _Scale(body["spec"]["replicas"], rv="2")


def test_kubernetes_scale_success():
    client = FakeAppsV1(replicas=3)
    ex = _live(KubernetesScalingExecutor(client, cluster="prod-a"))
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "applied" and r.post_state == 5 and client.patched == 5


def test_kubernetes_conflict():
    client = FakeAppsV1(replicas=7)  # actual != expected(3) -> conflict
    ex = _live(KubernetesScalingExecutor(client, cluster="prod-a"))
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "failed" and "expected" in (r.denial_reason or "")


def test_kubernetes_api_error():
    client = FakeAppsV1(replicas=3, error=True)
    ex = _live(KubernetesScalingExecutor(client, cluster="prod-a"))
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "failed"


def test_stale_pre_state_backend():
    # Backend observes a different current than the request's expected current.
    backend = FakeScalingBackend({"prod-a/web/frontend": 9})
    ex = _live(backend)
    r = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    assert r.outcome == "failed"  # ConcurrencyConflict


# ---- ArgoCD gate (fake http caller) ----

def _gate(http, mode=ExecutionMode.LIVE, base="https://argocd.internal"):
    cfg = OperationsConfig(mode=mode, target_policy=_tp(),
                           argocd_allowed_base_urls=(base,))
    return GateExecutor(cfg, http=http, verifier=support.verifier())


def test_argocd_sync_success():
    calls = []
    def http(method, url, headers, timeout):
        calls.append((method, url)); return (200, "ok")
    g = _gate(http)
    req = support.make_request(action="argocd_sync")
    authz = support.make_authorization(permitted_action="argocd_sync")
    out = g.sync(req, authz, base_url="https://argocd.internal", token="secret-token",
                 tenant_id="tenant-1")
    assert out.action == "sync" and out.applied is True and calls


def test_argocd_timeout_then_retry_exhaustion():
    def http(method, url, headers, timeout):
        raise TimeoutError("timed out")
    g = _gate(http)
    req = support.make_request(action="argocd_sync")
    authz = support.make_authorization(permitted_action="argocd_sync")
    out = g.sync(req, authz, base_url="https://argocd.internal", tenant_id="tenant-1")
    assert out.applied is False and "retry exhausted" in out.detail


def test_argocd_denied_without_authorization():
    def http(*a): return (200, "ok")
    g = _gate(http)
    out = g.sync(support.make_request(action="argocd_sync"), None,
                 base_url="https://argocd.internal", tenant_id="tenant-1")
    assert out.applied is False and out.action == "hold"


def test_argocd_base_url_not_allowlisted():
    def http(*a): return (200, "ok")
    g = _gate(http)
    out = g.sync(support.make_request(action="argocd_sync"),
                 support.make_authorization(permitted_action="argocd_sync"),
                 base_url="https://evil.example", tenant_id="tenant-1")
    assert out.applied is False


# ---- Idempotency / duplicate ----

def test_idempotent_retry_returns_duplicate():
    ex = _live(FakeScalingBackend({"prod-a/web/frontend": 3}))
    authz = support.make_authorization()
    r1 = ex.execute(support.make_request(), authz, tenant_id="tenant-1")
    r2 = ex.execute(support.make_request(), authz, tenant_id="tenant-1")
    assert r1.outcome == "applied" and r2.outcome == "duplicate" and r2.applied is False


# ---- Rollback ----

def test_rollback_success():
    ex = _live(FakeScalingBackend({"prod-a/web/frontend": 5}))
    authz = support.make_authorization()
    receipt = ex.execute(support.make_request(), authz, tenant_id="tenant-1")
    coord = RollbackCoordinator(ex)
    plan = RollbackPlan(prior_receipt=receipt, prior_state=5, target_state=3,
                        reason="revert", idempotency_key="rb-1")
    rb_authz = support.make_authorization(
        authorization_id="auth-rb", permitted_action="rollback",
        idempotency_key="rb-1", minimum_replicas=1, maximum_replicas=10, maximum_delta=5)
    res = coord.rollback(plan, RollbackAuthorization(authorization=rb_authz),
                         tenant_id="tenant-1")
    assert res.success and res.receipt.outcome == "applied" and res.receipt.post_state == 3


def test_rollback_outside_policy_bounds_denied():
    ex = _live(FakeScalingBackend({"prod-a/web/frontend": 5}))
    receipt = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    coord = RollbackCoordinator(ex)
    plan = RollbackPlan(prior_receipt=receipt, prior_state=5, target_state=99,
                        reason="revert", idempotency_key="rb-2")
    res = coord.rollback(plan, RollbackAuthorization(policy=RollbackPolicy(1, 10, 5)),
                         tenant_id="tenant-1")
    assert res.success is False and "policy bounds" in (res.denial_reason or "")


def test_rollback_without_authorization_denied():
    ex = _live(FakeScalingBackend({"prod-a/web/frontend": 5}))
    receipt = ex.execute(support.make_request(), support.make_authorization(), tenant_id="tenant-1")
    coord = RollbackCoordinator(ex)
    plan = RollbackPlan(prior_receipt=receipt, prior_state=5, target_state=3,
                        reason="revert", idempotency_key="rb-3")
    res = coord.rollback(plan, RollbackAuthorization(), tenant_id="tenant-1")
    assert res.success is False
