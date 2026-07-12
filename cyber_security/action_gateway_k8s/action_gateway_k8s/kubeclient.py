"""Minimal, shell-free Kubernetes REST client (stdlib only).

Talks to the apiserver over HTTPS with a CA bundle and either a client cert (the
broker's admin identity) or a bearer token (a scoped, broker-minted capability).
All requests are built structurally — there is NO shell string concatenation and
no ``kubectl`` subprocess on the execution path. Never logs tokens or secrets.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass


class K8sApiError(Exception):
    def __init__(self, status: int, body: dict):
        self.status = status
        self.body = body
        reason = body.get("reason", "") if isinstance(body, dict) else ""
        msg = body.get("message", "") if isinstance(body, dict) else str(body)
        self.reason = reason
        super().__init__(f"HTTP {status} {reason}: {msg}")


@dataclass
class GroupVersionResource:
    group: str          # "" for core
    version: str        # e.g. v1
    resource: str       # plural, e.g. configmaps, deployments
    namespaced: bool = True

    def collection_path(self, namespace: str | None) -> str:
        base = "/api/" + self.version if self.group == "" else f"/apis/{self.group}/{self.version}"
        if self.namespaced and namespace:
            return f"{base}/namespaces/{namespace}/{self.resource}"
        return f"{base}/{self.resource}"

    def object_path(self, namespace: str | None, name: str) -> str:
        return f"{self.collection_path(namespace)}/{name}"


# built-in resource map (unknown kinds fail closed in mapping.py, not here)
GVR = {
    "ConfigMap": GroupVersionResource("", "v1", "configmaps"),
    "Secret": GroupVersionResource("", "v1", "secrets"),
    "Service": GroupVersionResource("", "v1", "services"),
    "ServiceAccount": GroupVersionResource("", "v1", "serviceaccounts"),
    "Pod": GroupVersionResource("", "v1", "pods"),
    "Deployment": GroupVersionResource("apps", "v1", "deployments"),
    "Role": GroupVersionResource("rbac.authorization.k8s.io", "v1", "roles"),
    "RoleBinding": GroupVersionResource("rbac.authorization.k8s.io", "v1", "rolebindings"),
    "ClusterRole": GroupVersionResource("rbac.authorization.k8s.io", "v1", "clusterroles", False),
    "ClusterRoleBinding": GroupVersionResource("rbac.authorization.k8s.io", "v1",
                                               "clusterrolebindings", False),
    "NetworkPolicy": GroupVersionResource("networking.k8s.io", "v1", "networkpolicies"),
}


class KubeClient:
    def __init__(self, server: str, ca_cert: str, *, client_cert: str | None = None,
                 client_key: str | None = None, token: str | None = None):
        self.server = server.rstrip("/")
        self._token = token
        ctx = ssl.create_default_context(cafile=ca_cert)
        ctx.check_hostname = True
        if client_cert and client_key:
            ctx.load_cert_chain(certfile=client_cert, keyfile=client_key)
        self._ctx = ctx

    def _request(self, method: str, path: str, *, body=None, query=None,
                 content_type="application/json"):
        url = self.server + path
        if query:
            from urllib.parse import urlencode
            url += "?" + urlencode(query)
        data = None
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=20) as resp:
                raw = resp.read()
                if not raw:
                    return resp.status, {}
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, {"_raw": raw.decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            raw = e.read()
            parsed = {}
            try:
                parsed = json.loads(raw)
            except Exception:  # noqa: BLE001
                parsed = {"message": raw.decode("utf-8", "replace")}
            raise K8sApiError(e.code, parsed) from None

    # ---- typed operations ----

    def get(self, gvr: GroupVersionResource, namespace, name) -> dict:
        _, obj = self._request("GET", gvr.object_path(namespace, name))
        return obj

    def list(self, gvr: GroupVersionResource, namespace) -> dict:
        _, obj = self._request("GET", gvr.collection_path(namespace))
        return obj

    def apply(self, gvr: GroupVersionResource, namespace, name, manifest, *,
              dry_run=False, field_manager="action-gateway") -> dict:
        """Server-side apply (create-or-update). Set dry_run for admission-only."""
        query = {"fieldManager": field_manager, "force": "true"}
        if dry_run:
            query["dryRun"] = "All"
        _, obj = self._request(
            "PATCH", gvr.object_path(namespace, name), body=manifest, query=query,
            content_type="application/apply-patch+yaml")
        return obj

    def create(self, gvr: GroupVersionResource, namespace, obj, *, dry_run=False) -> dict:
        query = {"dryRun": "All"} if dry_run else None
        _, out = self._request("POST", gvr.collection_path(namespace), body=obj, query=query)
        return out

    def replace(self, gvr: GroupVersionResource, namespace, name, obj, *, dry_run=False) -> dict:
        query = {"dryRun": "All"} if dry_run else None
        _, out = self._request("PUT", gvr.object_path(namespace, name), body=obj, query=query)
        return out

    def delete(self, gvr: GroupVersionResource, namespace, name, *, dry_run=False,
               preconditions: dict | None = None) -> dict:
        query = {"dryRun": "All"} if dry_run else None
        body = None
        if preconditions:
            body = {"preconditions": preconditions}  # e.g. {resourceVersion, uid}
        _, out = self._request("DELETE", gvr.object_path(namespace, name),
                               body=body, query=query)
        return out

    def request_token(self, namespace, sa_name, *, audiences, expiration_seconds) -> dict:
        """Kubernetes TokenRequest API: mint a short-lived, audience-bound SA token."""
        gvr = GVR["ServiceAccount"]
        path = gvr.object_path(namespace, sa_name) + "/token"
        body = {"apiVersion": "authentication.k8s.io/v1", "kind": "TokenRequest",
                "spec": {"audiences": audiences, "expirationSeconds": expiration_seconds}}
        _, out = self._request("POST", path, body=body)
        return out  # {status: {token, expirationTimestamp}}

    def can_i(self, *, namespace, group, resource, verb, name=None,
              as_user=None, as_groups=None) -> bool:
        """SelfSubjectAccessReview / SubjectAccessReview (impersonation via as_user)."""
        body = {"apiVersion": "authorization.k8s.io/v1", "kind": "SubjectAccessReview",
                "spec": {"resourceAttributes": {"namespace": namespace, "group": group,
                                                "resource": resource, "verb": verb,
                                                "name": name}, "user": as_user,
                         "groups": as_groups or []}}
        _, out = self._request("POST", "/apis/authorization.k8s.io/v1/subjectaccessreviews",
                               body=body)
        return bool(out.get("status", {}).get("allowed"))
