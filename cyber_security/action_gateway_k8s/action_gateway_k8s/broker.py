"""Kubernetes credential broker.

The agent never holds a durable cluster credential. On an admissible decision the
broker mints the MINIMUM capability for the exact approved action:

  * a per-action ServiceAccount in the target namespace;
  * a Role scoped to the exact resource (``resourceNames``), verb set, and
    namespace, bound to that ServiceAccount;
  * a short-lived bearer token via the Kubernetes TokenRequest API.

Kubernetes natively binds: namespace, resource, name (for get/update/patch/
delete), verb, subject (SA), and expiry. The remaining application-level fields
(action hash, execution-token digest, nonce, policy hash, decision-record hash,
tool, operation) are bound in this trusted broker + the adapter — the trust
boundary is explicit (see README / IMPLEMENTATION_FINDINGS). RBAC ``resourceNames``
does not constrain ``create`` (an object has no name pre-creation), so for create
the exact name is enforced by the adapter, which only ever issues the approved
object path.

The bearer token is single-use: it never appears in the ``ScopedCredential`` object
or in any audit record, is redeemed exactly once, and the underlying RBAC is torn
down immediately after use so a leaked token cannot be replayed at the cluster.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from . import cluster as cluster_mod
from ._core import CredentialBroker, ScopedCredential, ref_hashing
from .kubeclient import GVR, K8sApiError
from action_gateway.clock import parse_ts
from action_gateway.errors import CredentialError

# frozen operation -> Kubernetes verb set (minimum for the operation)
_OP_VERBS = {
    "DEPLOY": ["get", "create", "patch", "update"],   # server-side apply
    "DB_DELETE": ["get", "delete"],
}


@dataclass(frozen=True)
class K8sCapabilityMeta:
    action_hash: str
    token_hash: str
    tool: str
    operation: str
    namespace: str
    kind: str
    name: str
    verbs: tuple
    nonce: str
    policy_hash: str
    decision_record_hash: str
    expires_at: str


def _parse_target(target: str):
    # "k8s://{namespace}/{kind}/{name}"
    _, rest = target.split("://", 1)
    ns, kind, name = rest.split("/", 2)
    return ns, kind, name


class KubernetesCredentialBroker(CredentialBroker):
    def __init__(self, admin_client=None, *, tool="kubernetes"):
        self._admin = admin_client
        self.tool = tool
        self._issued: dict[str, ScopedCredential] = {}
        self._secret: dict[str, str] = {}     # credential_id -> bearer token (never logged)
        self._meta: dict[str, K8sCapabilityMeta] = {}
        self._used: set[str] = set()
        self._teardown: dict[str, dict] = {}  # credential_id -> {sa, ns}
        self._counter = itertools.count(1)

    def _client(self):
        return self._admin or cluster_mod.admin_client()

    # ---- capability minting ----

    def issue(self, *, token, requested_permissions, principal, now) -> ScopedCredential:
        p = token["payload"]
        ns, kind, name = _parse_target(p["permitted_target"][0])
        op = p["permitted_operation"]
        if op not in _OP_VERBS:
            raise CredentialError(f"no k8s verb mapping for operation {op!r}")
        if kind not in GVR:
            raise CredentialError(f"unknown resource kind {kind!r}")
        # scope-expansion defence: the requested permissions may not exceed the
        # execution token's approved credential scope.
        token_scope = set(p.get("credential_scope", {}).get("permissions", []))
        for perm in requested_permissions:
            if perm not in token_scope and "*" not in token_scope:
                raise CredentialError(
                    f"requested permission {perm!r} exceeds approved credential scope")
        verbs = _OP_VERBS[op]
        gvr = GVR[kind]
        short = ref_hashing.domain_digest(
            "EXECUTION_TOKEN", token["token_hash"].encode("ascii"))[:12]
        sa = f"cap-{short}"
        admin = self._client()

        # 1. per-action ServiceAccount
        admin.create(GVR["ServiceAccount"], ns,
                     {"apiVersion": "v1", "kind": "ServiceAccount",
                      "metadata": {"name": sa, "namespace": ns,
                                   "labels": {"action-gateway.io/capability": "true"}}})
        # 2. minimal Role (resourceNames bind name for all verbs except create)
        named = [v for v in verbs if v != "create"]
        rules = []
        if named:
            rules.append({"apiGroups": [gvr.group], "resources": [gvr.resource],
                          "resourceNames": [name], "verbs": named})
        if "create" in verbs:
            rules.append({"apiGroups": [gvr.group], "resources": [gvr.resource],
                          "verbs": ["create"]})
        admin.create(GVR["Role"], ns,
                     {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role",
                      "metadata": {"name": sa, "namespace": ns}, "rules": rules})
        # 3. RoleBinding
        admin.create(GVR["RoleBinding"], ns,
                     {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
                      "metadata": {"name": sa, "namespace": ns},
                      "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role",
                                  "name": sa},
                      "subjects": [{"kind": "ServiceAccount", "name": sa, "namespace": ns}]})
        # 4. short-lived token (cluster floor is 600s; broker enforces the tighter
        #    execution-token expiry independently in validate()).
        tr = admin.request_token(ns, sa, audiences=["https://kubernetes.default.svc"],
                                 expiration_seconds=600)
        bearer = tr["status"]["token"]

        cid = f"k8scap-{next(self._counter)}"
        cred = ScopedCredential(
            credential_id=cid, principal=principal,
            permissions=frozenset(requested_permissions),
            token_hash=token["token_hash"], expires_at=p["expiration"])
        self._issued[cid] = cred
        self._secret[cid] = bearer
        self._meta[cid] = K8sCapabilityMeta(
            action_hash=p["action_hash"], token_hash=token["token_hash"], tool=self.tool,
            operation=op, namespace=ns, kind=kind, name=name, verbs=tuple(verbs),
            nonce=p["nonce"], policy_hash=p["policy_hash"],
            decision_record_hash=p["decision_record_hash"], expires_at=p["expiration"])
        self._teardown[cid] = {"sa": sa, "ns": ns}
        return cred

    # ---- validation / redemption ----

    def _check(self, credential: ScopedCredential, *, needed_permission, now):
        known = self._issued.get(credential.credential_id)
        if known is None or known != credential:
            raise CredentialError("unknown or forged capability")
        if credential.credential_id in self._used:
            raise CredentialError("capability already used (single-use)")
        if parse_ts(now) >= parse_ts(credential.expires_at):
            raise CredentialError("capability expired")
        perms = credential.permissions
        if needed_permission not in perms and "*" not in perms:
            raise CredentialError(f"capability lacks permission {needed_permission!r}")

    def validate(self, credential: ScopedCredential, *, needed_permission, now,
                 consume=False) -> bool:
        self._check(credential, needed_permission=needed_permission, now=now)
        if consume:
            self._used.add(credential.credential_id)
        return True

    def redeem(self, credential: ScopedCredential, *, needed_permission, now):
        """Single-use: validate, mark used, and return (bearer_token, meta)."""
        self._check(credential, needed_permission=needed_permission, now=now)
        self._used.add(credential.credential_id)
        return self._secret[credential.credential_id], self._meta[credential.credential_id]

    def meta(self, credential: ScopedCredential) -> K8sCapabilityMeta:
        return self._meta[credential.credential_id]

    def cleanup(self, credential: ScopedCredential) -> None:
        """Tear down the per-action RBAC + SA so a leaked token cannot be replayed."""
        td = self._teardown.get(credential.credential_id)
        if not td:
            return
        admin = self._client()
        for kind in ("RoleBinding", "Role", "ServiceAccount"):
            try:
                admin.delete(GVR[kind], td["ns"], td["sa"])
            except K8sApiError:
                pass
        self._secret.pop(credential.credential_id, None)

    def revoke(self, credential: ScopedCredential) -> None:
        self._used.add(credential.credential_id)
        self.cleanup(credential)
