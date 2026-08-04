"""Kubernetes scaling backend (injected client; no credentials at import).

Implements the :class:`~ugence_cloud_scaling_operations.executors.ScalingBackend`
interface against an injected AppsV1Api-like client. The real Kubernetes SDK is an
optional dependency (the ``kubernetes`` extra) and is only touched if no client is
injected AND a live client is explicitly requested. Deterministic fake clients drive
tests.
"""

from __future__ import annotations

from typing import Dict, Optional, Protocol, runtime_checkable

from .executors import ConcurrencyConflict


@runtime_checkable
class AppsV1ScaleClient(Protocol):
    """Subset of kubernetes.client.AppsV1Api used here (duck-typed)."""

    def read_namespaced_deployment_scale(self, name: str, namespace: str):
        ...

    def patch_namespaced_deployment_scale(self, name: str, namespace: str, body):
        ...


class KubernetesScalingExecutor:
    """A ScalingBackend backed by an injected AppsV1Api-like client.

    Requires explicit cluster + namespace; reads current scale, verifies the expected
    pre-state, applies only the authorized target, detects optimistic-concurrency
    conflicts, and returns the structured API response. Never selects the current
    kubectl context and never loads credentials at import.
    """

    def __init__(self, client: Optional[AppsV1ScaleClient] = None, *, cluster: str = ""):
        self._client = client
        self._cluster = cluster

    def _require_client(self) -> AppsV1ScaleClient:
        if self._client is None:  # pragma: no cover - exercised only without injection
            raise RuntimeError(
                "KubernetesScalingExecutor requires an injected AppsV1Api client. "
                "Install the optional extra and construct a client explicitly: "
                "pip install ugence-cloud-scaling-operations[kubernetes]")
        return self._client

    def read_replicas(self, cluster: str, namespace: str, resource: str) -> int:
        if not namespace or not resource:
            raise ValueError("explicit namespace and resource are required")
        scale = self._require_client().read_namespaced_deployment_scale(resource, namespace)
        return int(scale.spec.replicas)

    def set_replicas(self, cluster: str, namespace: str, resource: str,
                     target: int, expected_current: int) -> Dict:
        if not namespace or not resource:
            raise ValueError("explicit namespace and resource are required")
        client = self._require_client()
        # Verify expected pre-state (optimistic concurrency).
        current = int(client.read_namespaced_deployment_scale(resource, namespace).spec.replicas)
        if current != expected_current:
            raise ConcurrencyConflict(
                f"pre-state {current} != expected {expected_current} for "
                f"{namespace}/{resource}")
        body = {"spec": {"replicas": int(target)}}
        resp = client.patch_namespaced_deployment_scale(resource, namespace, body)
        replicas = getattr(getattr(resp, "spec", None), "replicas", target)
        return {"replicas": int(replicas), "resourceVersion":
                getattr(getattr(resp, "metadata", None), "resource_version", None)}


__all__ = ["KubernetesScalingExecutor", "AppsV1ScaleClient"]
