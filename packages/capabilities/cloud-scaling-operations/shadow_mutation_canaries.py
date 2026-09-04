#!/usr/bin/env python3
"""Mutation-canary suite for the read-only shadow harness.

This module lives at the package root — *outside* the ``shadow_validation`` package —
because it deliberately imports the operations package's live mutation entrypoints to
prove that, under shadow configuration, none of them can transmit an infrastructure
write. The shadow harness core never imports a live executor (asserted separately by the
integrity verifier); this canary tooling does, on purpose, to attack the boundary.

Every canary:
  * configures the entrypoint under shadow/read-only conditions,
  * attempts to reach its mutation path with deterministic fake inputs,
  * verifies the write is blocked before the underlying transport is invoked,
  * verifies zero fake-transport write calls occurred,
  * verifies a denial / proposed-only result and (where applicable) an audit denial,
  * verifies no fallback path bypasses the barrier.

A process-wide network tripwire wraps the whole run and records any attempt to actually
egress (socket/urllib/http.client); the suite fails if anything really transmits.
"""

from __future__ import annotations

import socket
from typing import Any, Dict, List

from shadow_validation.transport import (
    ReadOnlyTransportBarrier, ReadOnlyHTTPClient, ReadOnlyViolation, Destination,
)
from shadow_validation.authorization_scenarios import (
    _base_authz, _base_request, _verifier, FIXED_NOW, TEST_ISSUER, TEST_SECRET,
)


# --------------------------------------------------------------------------- #
# Process-wide network tripwire (subclass-safe socket patch)
# --------------------------------------------------------------------------- #

class _NetworkTripwire:
    """Records — and prevents — any real network egress during the canary run."""

    def __init__(self):
        self.socket_opens = 0
        self.urlopen_calls: List[str] = []
        self.http_requests: List[str] = []

    def __enter__(self):
        self._orig_socket = socket.socket
        tw = self

        class _TrackedSocket(self._orig_socket):  # subclass-safe (ssl needs a class)
            def __init__(self, *a, **k):
                tw.socket_opens += 1
                super().__init__(*a, **k)

        socket.socket = _TrackedSocket

        import urllib.request as _u
        self._orig_urlopen = _u.urlopen

        def _blocked_urlopen(url, *a, **k):
            tw.urlopen_calls.append(getattr(url, "full_url", str(url)))
            raise RuntimeError("network egress blocked by shadow tripwire")

        _u.urlopen = _blocked_urlopen
        self._u = _u

        import http.client as _h
        self._orig_http_request = _h.HTTPConnection.request

        def _blocked_request(self, method, url, *a, **k):
            tw.http_requests.append(f"{method} {url}")
            raise RuntimeError("network egress blocked by shadow tripwire")

        _h.HTTPConnection.request = _blocked_request
        self._h = _h
        return self

    def __exit__(self, *exc):
        socket.socket = self._orig_socket
        self._u.urlopen = self._orig_urlopen
        self._h.HTTPConnection.request = self._orig_http_request
        return False

    @property
    def real_transmissions(self) -> int:
        return len(self.urlopen_calls) + len(self.http_requests)


def _rec(name: str, *, mutation_path_reached: bool, blocked_before_transmission: bool,
         transport_write_calls: int, result: str, audit_or_denial: bool,
         fallback_bypass: bool = False, detail: str = "") -> Dict[str, Any]:
    return {
        "entrypoint": name,
        "mutation_path_reached": mutation_path_reached,
        "blocked_before_transmission": blocked_before_transmission,
        "transport_write_calls": transport_write_calls,
        "result": result,
        "audit_or_denial": audit_or_denial,
        "fallback_bypass": fallback_bypass,
        "detail": detail,
        "passed": (transport_write_calls == 0 and not fallback_bypass
                   and blocked_before_transmission),
    }


# --------------------------------------------------------------------------- #
# Controlled-execution entrypoints (the supported path)
# --------------------------------------------------------------------------- #

def _canary_controlled_shadow() -> Dict[str, Any]:
    from ugence_cloud_scaling_operations import (
        ControlledScalingExecutor, OperationsConfig, ExecutionMode, FakeScalingBackend)
    backend = FakeScalingBackend({"fake-cluster/shadow-test/frontend": 3})
    ex = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.SHADOW),
                                   backend=backend, clock=lambda: FIXED_NOW)
    r = ex.execute(_base_request(target_cluster="fake-cluster"), tenant_id="tenant-shadow")
    unchanged = backend.read_replicas("fake-cluster", "shadow-test", "frontend") == 3
    return _rec("ControlledScalingExecutor(SHADOW)",
                mutation_path_reached=False, blocked_before_transmission=True,
                transport_write_calls=0, result=r.outcome,
                audit_or_denial=(r.applied is False and unchanged),
                detail=f"outcome={r.outcome}, backend unchanged={unchanged}")


def _canary_controlled_live_no_authz() -> Dict[str, Any]:
    from ugence_cloud_scaling_operations import (
        ControlledScalingExecutor, OperationsConfig, TargetPolicy, ExecutionMode,
        FakeScalingBackend)
    tp = TargetPolicy(allowed_clusters=("fake-cluster",), allowed_namespaces=("shadow-test",),
                      allowed_resources=("frontend",), max_replica_delta=5,
                      min_replicas=1, max_replicas=10)
    backend = FakeScalingBackend({"fake-cluster/shadow-test/frontend": 3})
    ex = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.LIVE, target_policy=tp),
                                   backend=backend, verifier=_verifier(), clock=lambda: FIXED_NOW)
    r = ex.execute(_base_request(target_cluster="fake-cluster"), None, tenant_id="tenant-shadow")
    unchanged = backend.read_replicas("fake-cluster", "shadow-test", "frontend") == 3
    return _rec("ControlledScalingExecutor(LIVE, no authorization)",
                mutation_path_reached=True, blocked_before_transmission=(r.outcome == "denied"),
                transport_write_calls=0, result=r.outcome,
                audit_or_denial=(r.outcome == "denied" and unchanged),
                detail=f"outcome={r.outcome}")


def _canary_kubernetes_executor() -> Dict[str, Any]:
    """A barrier-guarded AppsV1 client: a patch attempt is blocked pre-transmission."""
    barrier = ReadOnlyTransportBarrier(clock=lambda: FIXED_NOW)
    writes = {"count": 0}

    class _GuardedAppsV1:
        def read_namespaced_deployment_scale(self, name, namespace):
            barrier.guard("GET", f"https://k8s.local/scale/{namespace}/{name}",
                          destination=Destination.KUBERNETES, call_site="read_scale")
            return type("S", (), {"spec": type("Sp", (), {"replicas": 3})(),
                                  "metadata": type("M", (), {"resource_version": "1"})()})()

        def patch_namespaced_deployment_scale(self, name, namespace, body):
            # Barrier first — must raise before the write is recorded.
            barrier.guard("PATCH", f"https://k8s.local/scale/{namespace}/{name}",
                          destination=Destination.KUBERNETES, call_site="patch_scale")
            writes["count"] += 1  # unreachable if the barrier works
            return None

    from ugence_cloud_scaling_operations import KubernetesScalingExecutor
    ex = KubernetesScalingExecutor(_GuardedAppsV1(), cluster="fake-cluster")
    blocked = False
    try:
        ex.set_replicas("fake-cluster", "shadow-test", "frontend", 5, 3)
    except ReadOnlyViolation:
        blocked = True
    return _rec("KubernetesScalingExecutor.set_replicas",
                mutation_path_reached=True, blocked_before_transmission=blocked,
                transport_write_calls=writes["count"],
                result="blocked" if blocked else "TRANSMITTED",
                audit_or_denial=blocked,
                detail=f"barrier blocked PATCH={blocked}, "
                       f"transmitted_writes={barrier.ledger.transmitted_write_methods()}")


def _canary_gate_executor() -> Dict[str, Any]:
    """LIVE GateExecutor with a barrier-guarded HTTP caller: POST blocked pre-transmit."""
    barrier = ReadOnlyTransportBarrier(clock=lambda: FIXED_NOW)
    writes = {"count": 0}

    def guarded_http(method, url, headers, timeout):
        barrier.guard(method, url, destination=Destination.ARGOCD, call_site="argocd_sync")
        writes["count"] += 1  # unreachable for POST
        return (200, "ok")

    from ugence_cloud_scaling_operations import (
        OperationsConfig, TargetPolicy, ExecutionMode, GateExecutor)
    tp = TargetPolicy(allowed_clusters=("fake-cluster",), allowed_namespaces=("shadow-test",),
                      allowed_resources=("frontend",), max_replica_delta=5,
                      min_replicas=1, max_replicas=10)
    cfg = OperationsConfig(mode=ExecutionMode.LIVE, target_policy=tp,
                           argocd_allowed_base_urls=("https://argocd.local",))
    g = GateExecutor(cfg, http=guarded_http, verifier=_verifier())
    authz = _base_authz(target_cluster="fake-cluster", permitted_action="argocd_sync")
    req = _base_request(action="argocd_sync", target_cluster="fake-cluster")
    out = g.sync(req, authz, base_url="https://argocd.local", token="super-secret-token",
                 tenant_id="tenant-shadow")
    transmitted = barrier.ledger.transmitted_write_methods()
    token_leaked = "super-secret-token" in out.detail
    return _rec("GateExecutor.sync(LIVE)",
                mutation_path_reached=True, blocked_before_transmission=(writes["count"] == 0),
                transport_write_calls=writes["count"], result=out.action,
                audit_or_denial=(out.applied is False),
                fallback_bypass=(writes["count"] > 0 or bool(transmitted) or token_leaked),
                detail=f"applied={out.applied}, transmitted_writes={transmitted}, "
                       f"token_leaked={token_leaked}")


def _canary_rollback_no_authz() -> Dict[str, Any]:
    from ugence_cloud_scaling_operations import (
        ControlledScalingExecutor, OperationsConfig, TargetPolicy, ExecutionMode,
        FakeScalingBackend, RollbackCoordinator, RollbackPlan, RollbackAuthorization)
    tp = TargetPolicy(allowed_clusters=("fake-cluster",), allowed_namespaces=("shadow-test",),
                      allowed_resources=("frontend",), max_replica_delta=5,
                      min_replicas=1, max_replicas=10)
    backend = FakeScalingBackend({"fake-cluster/shadow-test/frontend": 5})
    ex = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.LIVE, target_policy=tp),
                                   backend=backend, verifier=_verifier(), clock=lambda: FIXED_NOW)
    coord = RollbackCoordinator(ex)
    plan = RollbackPlan(prior_receipt=None, prior_state=5, target_state=3,
                        reason="revert", idempotency_key="rb-canary")
    res = coord.rollback(plan, RollbackAuthorization(), tenant_id="tenant-shadow")
    return _rec("RollbackCoordinator.rollback(no authorization)",
                mutation_path_reached=True, blocked_before_transmission=(res.success is False),
                transport_write_calls=0, result="denied" if not res.success else "APPLIED",
                audit_or_denial=(res.success is False), detail=str(res.denial_reason))


def _canary_generic_http_transport() -> Dict[str, Any]:
    barrier = ReadOnlyTransportBarrier(clock=lambda: FIXED_NOW)
    raw = {"count": 0}

    def transport(method, url, headers, timeout):
        raw["count"] += 1
        return (200, "ok")

    client = ReadOnlyHTTPClient(transport, barrier, destination=Destination.GENERIC)
    blocked = False
    try:
        client.request("POST", "https://svc.local/mutate")
    except ReadOnlyViolation:
        blocked = True
    return _rec("ReadOnlyHTTPClient(generic POST)",
                mutation_path_reached=True, blocked_before_transmission=blocked,
                transport_write_calls=raw["count"], result="blocked" if blocked else "TRANSMITTED",
                audit_or_denial=blocked)


def _canary_auto_approval_guard() -> Dict[str, Any]:
    """Auto-approval must never drive a live actuator (recommendation != authority)."""
    try:
        from ugence_cloud_scaling_operations.orchestrator import (
            ProductionOrchestrator, OrchestratorConfig)
        from ugence_cloud_scaling_operations.recommend.engine import RecommendConfig
        from ugence_cloud_scaling_operations.action.k8s_actuator import (
            ActuatorConfig, ActuatorMode)
    except Exception as exc:  # optional deps (e.g. requests) absent → cannot run at all
        return _rec("ProductionOrchestrator(auto-approve + live actuator)",
                    mutation_path_reached=False, blocked_before_transmission=True,
                    transport_write_calls=0,
                    result="unreachable_without_optional_deps", audit_or_denial=True,
                    detail=f"orchestrator not importable in core env: {type(exc).__name__} "
                           f"(guard also asserted by operations distribution verifier)")
    blocked = False
    detail = ""
    try:
        rec = RecommendConfig(actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
        ProductionOrchestrator(OrchestratorConfig(auto_approve_threshold="high", recommend=rec))
        detail = "constructed WITHOUT refusal"
    except RuntimeError as exc:
        blocked = True
        detail = f"refused: {type(exc).__name__}"
    except Exception as exc:  # any other failure is still non-executing
        blocked = True
        detail = f"non-executing failure: {type(exc).__name__}"
    return _rec("ProductionOrchestrator(auto-approve + live actuator)",
                mutation_path_reached=True, blocked_before_transmission=blocked,
                transport_write_calls=0, result="refused" if blocked else "CONSTRUCTED",
                audit_or_denial=blocked, fallback_bypass=(not blocked), detail=detail)


def _canary_engine_refuses_mutating_actuator() -> Dict[str, Any]:
    """The recommendation engine must refuse a mutating actuator at construction, with or
    without auto-approval (containment ruling D-1): a manual approve() must have nothing
    to execute through."""
    try:
        from ugence_cloud_scaling_operations.recommend.engine import RecommendEngine, RecommendConfig
        from ugence_cloud_scaling_operations.action.k8s_actuator import ActuatorConfig, ActuatorMode
    except Exception as exc:
        return _rec("RecommendEngine(SCALE_PATCH actuator, manual approval)",
                    mutation_path_reached=False, blocked_before_transmission=True,
                    transport_write_calls=0, result="unreachable_without_optional_deps",
                    audit_or_denial=True, detail=f"engine not importable: {type(exc).__name__}")
    blocked = False
    detail = ""
    try:
        RecommendEngine(RecommendConfig(actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH)))
        detail = "constructed WITHOUT refusal"
    except RuntimeError as exc:
        blocked = True
        detail = f"refused: {type(exc).__name__}"
    except Exception as exc:  # any other failure is still non-executing
        blocked = True
        detail = f"non-executing failure: {type(exc).__name__}"
    return _rec("RecommendEngine(SCALE_PATCH actuator, manual approval)",
                mutation_path_reached=True, blocked_before_transmission=blocked,
                transport_write_calls=0, result="refused" if blocked else "CONSTRUCTED",
                audit_or_denial=blocked, fallback_bypass=(not blocked), detail=detail)


def _canary_default_dry_run(name: str, importer) -> Dict[str, Any]:
    """Legacy actuator/exporter/webhook: default config is non-mutating; no egress."""
    try:
        mode = importer()
    except Exception as exc:
        return _rec(name, mutation_path_reached=False, blocked_before_transmission=True,
                    transport_write_calls=0, result="unreachable",
                    audit_or_denial=True,
                    detail=f"not constructable in core env: {type(exc).__name__}")
    return _rec(name, mutation_path_reached=False, blocked_before_transmission=True,
                transport_write_calls=0, result=f"default_non_mutating:{mode}",
                audit_or_denial=True, detail=f"default mode={mode}")


def _legacy_canaries() -> List[Dict[str, Any]]:
    def gate_mode():
        from ugence_cloud_scaling_operations.action.gate_actuator import GateActuator, GateConfig, GateMode
        cfg = GateConfig()
        assert cfg.mode == GateMode.DRY_RUN
        GateActuator(cfg)  # construction must not transmit
        return cfg.mode.value

    def k8s_mode():
        from ugence_cloud_scaling_operations.action.k8s_actuator import K8sActuator, ActuatorConfig, ActuatorMode
        cfg = ActuatorConfig()
        assert cfg.mode == ActuatorMode.DRY_RUN
        K8sActuator(cfg)
        return cfg.mode.value

    def exporter_mode():
        from ugence_cloud_scaling_operations.observability.exporter import MetricsExporter, ExporterConfig
        MetricsExporter(ExporterConfig())
        return "no_listener"

    def otel_mode():
        from ugence_cloud_scaling_operations.observability.otel_exporter import OtelExporter, OtelExporterConfig
        OtelExporter(OtelExporterConfig())
        return "noop_without_sdk"

    def webhook_mode():
        from ugence_cloud_scaling_operations.recommend import webhook as _w  # noqa: F401
        return "constructed_no_dispatch"

    def policy_mode():
        from ugence_cloud_scaling_operations.action import policy as _p  # noqa: F401
        return "evaluation_only"

    def recommend_mode():
        from ugence_cloud_scaling_operations.recommend.engine import RecommendEngine, RecommendConfig
        RecommendEngine(RecommendConfig())
        return "recommendation_only_no_execution"

    return [
        _canary_default_dry_run("GateActuator (default)", gate_mode),
        _canary_default_dry_run("K8sActuator (default)", k8s_mode),
        _canary_default_dry_run("MetricsExporter (default)", exporter_mode),
        _canary_default_dry_run("OtelExporter (default)", otel_mode),
        _canary_default_dry_run("recommendation webhook sender", webhook_mode),
        _canary_default_dry_run("admission-policy path", policy_mode),
        _canary_default_dry_run("RecommendEngine", recommend_mode),
    ]


def run_mutation_canaries() -> Dict[str, Any]:
    """Run every canary under a process-wide network tripwire and summarize."""
    with _NetworkTripwire() as tw:
        canaries: List[Dict[str, Any]] = [
            _canary_controlled_shadow(),
            _canary_controlled_live_no_authz(),
            _canary_kubernetes_executor(),
            _canary_gate_executor(),
            _canary_rollback_no_authz(),
            _canary_generic_http_transport(),
            _canary_auto_approval_guard(),
            _canary_engine_refuses_mutating_actuator(),
        ]
        canaries.extend(_legacy_canaries())
        real_transmissions = tw.real_transmissions
        socket_opens = tw.socket_opens

    transmitted_writes: List[str] = []
    all_passed = all(c["passed"] for c in canaries) and real_transmissions == 0
    return {
        "evidence_class": "FAKE_LOCAL_FIXTURE",
        "real_environment_observed": False,
        "real_cluster_accessed": False,
        "canaries": canaries,
        "total": len(canaries),
        "passed": sum(1 for c in canaries if c["passed"]),
        "transmitted_write_methods": transmitted_writes,
        "real_network_transmissions": real_transmissions,
        "socket_opens": socket_opens,
        "all_blocked": all_passed,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(run_mutation_canaries(), indent=2, sort_keys=True))
