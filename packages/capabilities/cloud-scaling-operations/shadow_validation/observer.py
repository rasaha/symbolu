"""Bounded, read-only observer over *injected* client interfaces.

The observer never instantiates a real Kubernetes or ArgoCD client, never loads a
kubeconfig, never reads in-cluster/service-account credentials, and never discovers the
current context. It operates only through injected read-only clients, and every remote
read is funneled through the transport barrier so the request-method ledger stays
complete. Only scaling-relevant fields are collected; secrets are never exposed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Sequence, runtime_checkable

from .allowlist import TargetAllowlist, TargetRef
from .contracts import (
    DeploymentObservation,
    Destination,
    EventSummary,
    HorizontalPodAutoscalerObservation,
    MetricsObservation,
    PodSummary,
)
from .redaction import redact_exception
from .transport import ReadOnlyTransportBarrier


# --------------------------------------------------------------------------- #
# Injected read-only client interfaces (Protocols — no real SDK imported here)
# --------------------------------------------------------------------------- #

@runtime_checkable
class ReadOnlyKubernetesClient(Protocol):
    def read_deployment(self, namespace: str, name: str) -> DeploymentObservation: ...
    def list_deployments(self, namespace: str) -> List[DeploymentObservation]: ...
    def read_hpa(self, namespace: str, name: str
                 ) -> Optional[HorizontalPodAutoscalerObservation]: ...
    def list_pods(self, namespace: str) -> List[PodSummary]: ...
    def list_events(self, namespace: str) -> List[EventSummary]: ...


@runtime_checkable
class ReadOnlyMetricsClient(Protocol):
    def get_metrics(self, namespace: str, name: str) -> Optional[MetricsObservation]: ...


@runtime_checkable
class ReadOnlyWatchClient(Protocol):
    def watch_deployments(self, namespace: str) -> Sequence[DeploymentObservation]: ...


@runtime_checkable
class ReadOnlyArgoCDClient(Protocol):
    def get_application(self, name: str) -> dict: ...


# --------------------------------------------------------------------------- #
# Bounded, read-only retry
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.0  # deterministic (0) by default for reproducible fixtures


class ObservationError(Exception):
    """Redacted read failure after bounded retries (never triggers a mutation)."""


def bounded_read(fn: Callable[[], object], policy: RetryPolicy,
                 sleep: Callable[[float], None] = lambda _s: None):
    """Run a read-only ``fn`` with bounded retries. Errors are redacted; retries never
    escalate to a write."""
    last: Optional[BaseException] = None
    for attempt in range(1, max(1, policy.max_attempts) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — read errors are contained + redacted
            last = exc
            if attempt < policy.max_attempts:
                sleep(policy.backoff_seconds)
    raise ObservationError(redact_exception(last) if last else "read failed")


# --------------------------------------------------------------------------- #
# Fake read-only clients (fixtures/tests) — route reads through the barrier
# --------------------------------------------------------------------------- #

class FakeReadOnlyKubernetesClient:
    """Deterministic fake that records read verbs through the barrier.

    ``deployments`` / ``hpas`` map ``"namespace/name" -> observation``. ``fault`` is an
    optional callable ``(op, namespace, name) -> None`` that may raise to simulate
    network conditions; it runs *after* the barrier records the read attempt.
    """

    def __init__(self, barrier: ReadOnlyTransportBarrier, *, cluster: str,
                 base_url: str = "https://fake-apiserver.local",
                 deployments=None, hpas=None, pods=None, events=None, fault=None):
        self._b = barrier
        self._cluster = cluster
        self._base = base_url
        self._deployments = dict(deployments or {})
        self._hpas = dict(hpas or {})
        self._pods = dict(pods or {})
        self._events = dict(events or {})
        self._fault = fault

    def _read(self, method: str, path: str, op: str, namespace: str, name: str):
        self._b.guard(method, f"{self._base}{path}", destination=Destination.KUBERNETES,
                      call_site=f"FakeReadOnlyKubernetesClient.{op}")
        if self._fault:
            self._fault(op, namespace, name)

    def read_deployment(self, namespace: str, name: str) -> DeploymentObservation:
        self._read("GET",
                   f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}/scale",
                   "read_deployment", namespace, name)
        obs = self._deployments.get(f"{namespace}/{name}")
        if obs is None:
            raise KeyError(f"deployment {namespace}/{name} not found")
        return obs

    def list_deployments(self, namespace: str) -> List[DeploymentObservation]:
        self._read("LIST", f"/apis/apps/v1/namespaces/{namespace}/deployments",
                   "list_deployments", namespace, "")
        return [o for k, o in self._deployments.items() if k.startswith(f"{namespace}/")]

    def read_hpa(self, namespace: str, name: str):
        self._read("GET",
                   f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{name}",
                   "read_hpa", namespace, name)
        return self._hpas.get(f"{namespace}/{name}")

    def list_pods(self, namespace: str) -> List[PodSummary]:
        self._read("LIST", f"/api/v1/namespaces/{namespace}/pods", "list_pods",
                   namespace, "")
        return list(self._pods.get(namespace, []))

    def list_events(self, namespace: str) -> List[EventSummary]:
        self._read("LIST", f"/api/v1/namespaces/{namespace}/events", "list_events",
                   namespace, "")
        return list(self._events.get(namespace, []))


class FakeReadOnlyMetricsClient:
    def __init__(self, barrier: ReadOnlyTransportBarrier, *,
                 base_url: str = "https://fake-metrics.local", metrics=None, fault=None):
        self._b = barrier
        self._base = base_url
        self._metrics = dict(metrics or {})
        self._fault = fault

    def get_metrics(self, namespace: str, name: str):
        self._b.guard("GET", f"{self._base}/metrics/{namespace}/{name}",
                      destination=Destination.METRICS,
                      call_site="FakeReadOnlyMetricsClient.get_metrics")
        if self._fault:
            self._fault("get_metrics", namespace, name)
        return self._metrics.get(f"{namespace}/{name}")


# --------------------------------------------------------------------------- #
# Observer
# --------------------------------------------------------------------------- #

class ShadowObserver:
    """Collects allowlisted, scaling-relevant state through injected read-only clients."""

    def __init__(self, client: ReadOnlyKubernetesClient, allowlist: TargetAllowlist, *,
                 metrics_client: Optional[ReadOnlyMetricsClient] = None,
                 retry: RetryPolicy = RetryPolicy(),
                 clock: Callable[[], float] = time.time):
        self._client = client
        self._allowlist = allowlist
        self._metrics = metrics_client
        self._retry = retry
        self._clock = clock

    def observe_deployment(self, target: TargetRef
                           ) -> DeploymentObservation:
        decision = self._allowlist.evaluate(target)
        if not decision.allowed:
            raise PermissionError(f"target not allowlisted: {decision.reason}")
        return bounded_read(
            lambda: self._client.read_deployment(target.namespace, target.resource_name),
            self._retry)

    def observe_hpa(self, target: TargetRef
                    ) -> Optional[HorizontalPodAutoscalerObservation]:
        return bounded_read(
            lambda: self._client.read_hpa(target.namespace, target.resource_name),
            self._retry)

    def observe_metrics(self, target: TargetRef) -> Optional[MetricsObservation]:
        if not self._metrics:
            return None
        return bounded_read(
            lambda: self._metrics.get_metrics(target.namespace, target.resource_name),
            self._retry)


# --------------------------------------------------------------------------- #
# Real-environment adapter (documented seam; never connects in this phase)
# --------------------------------------------------------------------------- #

class RealEnvironmentAdapter:
    """Wraps an *explicitly supplied* real read-only client.

    This class performs NO auto-discovery: it never calls ``load_kube_config`` /
    ``load_incluster_config``, never reads the current context, and never loads
    credentials. A caller must inject an already-constructed read-only client. In this
    harness-only phase it is never pointed at a remote endpoint.
    """

    def __init__(self, injected_client, *, explicit_config):
        if injected_client is None:
            raise ValueError(
                "RealEnvironmentAdapter requires an explicitly injected read-only "
                "client; auto-discovery of kubeconfig/context/credentials is refused")
        if explicit_config is None:
            raise ValueError("RealEnvironmentAdapter requires an explicit config")
        self._client = injected_client
        self._config = explicit_config


def refuse_auto_discovery(*_a, **_k):
    """Any attempt to auto-build a real client is refused (fail closed)."""
    raise RuntimeError(
        "the shadow harness never auto-discovers cluster credentials or context; "
        "inject an explicit read-only client via RealEnvironmentAdapter")


__all__ = [
    "ReadOnlyKubernetesClient",
    "ReadOnlyMetricsClient",
    "ReadOnlyWatchClient",
    "ReadOnlyArgoCDClient",
    "RetryPolicy",
    "ObservationError",
    "bounded_read",
    "FakeReadOnlyKubernetesClient",
    "FakeReadOnlyMetricsClient",
    "ShadowObserver",
    "RealEnvironmentAdapter",
    "refuse_auto_discovery",
]
