"""Real Kubernetes execution adapter.

Runs ONLY inside the gateway/broker trust domain. It redeems a single-use,
broker-minted capability, builds a scoped ``KubeClient`` from the ephemeral bearer
token, performs the exact approved API operation against the real cluster, then
tears the capability down. It never receives a durable credential, never shells
out, and never logs the token or secret contents.
"""

from __future__ import annotations

import json

from . import cluster as cluster_mod
from .kubeclient import GVR, KubeClient
from action_gateway.adapters import ToolAdapter
from action_gateway.errors import AdapterError


def _stringify(v):
    """Coerce bare numbers to strings so the Action-Profile result hasher accepts
    the returned object (JSON numbers like replicas/ports are otherwise rejected)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return {k: _stringify(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_stringify(x) for x in v]
    return v


def _redact(obj: dict) -> dict:
    """Drop Secret payloads from any object before it is returned/audited."""
    if not isinstance(obj, dict):
        return obj
    if obj.get("kind") == "Secret":
        o = dict(obj)
        for k in ("data", "stringData"):
            if k in o:
                o[k] = {key: "[REDACTED]" for key in o[k]}
        return o
    return obj


class KubernetesAdapter(ToolAdapter):
    name = "kubernetes"

    def __init__(self, *, server=None, ca_cert=None):
        self.server = server or cluster_mod.SERVER
        self.ca_cert = ca_cert or str(cluster_mod.CA_CERT)

    def execute(self, req, credential, *, broker, now) -> dict:
        needed = self.needed_permission(req.verb)
        bearer, meta = broker.redeem(credential, needed_permission=needed, now=now)
        try:
            client = KubeClient(self.server, self.ca_cert, token=bearer)
            result = self._perform(req, meta, client)
        finally:
            broker.cleanup(credential)  # single-use at the cluster: RBAC torn down
        return result

    def _perform(self, req, meta, client) -> dict:
        gvr = GVR[meta.kind]
        ns, name = meta.namespace, meta.name
        if req.verb == "apply":
            mj = req.args.get("manifest_json")
            if not mj:
                raise AdapterError("apply requires a bound manifest")
            manifest = json.loads(mj)  # the exact manifest bound into the action hash
            obj = client.apply(gvr, ns, name, manifest)
            return self._ok("apply", meta, obj)
        if req.verb == "delete":
            pre = None
            rv = req.args.get("resource_version")
            if rv:
                pre = {"resourceVersion": rv}
            obj = client.delete(gvr, ns, name, preconditions=pre)
            return self._ok("delete", meta, obj)
        if req.verb == "get":
            obj = client.get(gvr, ns, name)
            return self._ok("get", meta, obj)
        raise AdapterError(f"kubernetes adapter: unsupported verb {req.verb!r}")

    @staticmethod
    def _ok(verb, meta, obj) -> dict:
        obj = _stringify(_redact(obj))  # Action-Profile-safe (strings only)
        return {"status": "ok", "verb": verb, "kind": meta.kind, "name": meta.name,
                "namespace": meta.namespace, "mocked": "false",
                "resource_version": obj.get("metadata", {}).get("resourceVersion", ""),
                "uid": obj.get("metadata", {}).get("uid", ""),
                "object": obj}
