"""Credential broker / execution service — the ONLY holder of privileged K8s authority.

Verifies asymmetric authorization independently, claims durable single-use nonces,
mints a per-action resource/verb-scoped short-lived credential, performs a
CONDITIONAL (optimistic-concurrency) write that closes the commit-time TOCTOU race,
tears the credential down and VERIFIES the teardown (never swallowed), and appends
a hash-chained audit record. It exposes no bearer credential to the gateway/agent.
"""

from __future__ import annotations

from . import authz, policy_semantic
from ._core import GVR, K8sApiError, KubeClient, ref_hashing
from .audit_ledger import AuditLedger
from .replaystore import ReplayStore

# write verb sets per operation (minimum authority)
_VERBS = {"create": ["create"], "update": ["get", "update"], "delete": ["get", "delete"]}


class BrokerError(Exception):
    def __init__(self, code, message=""):
        self.code = code
        super().__init__(f"{code}: {message}")


class BrokerCore:
    def __init__(self, *, admin_client, keyring, active_policy_hash, replay_db, audit_db,
                 server, ca_cert, clock, allowed_namespaces=("protected",),
                 gateway_identity):
        self.admin = admin_client
        self.keyring = keyring
        self.active_policy_hash = active_policy_hash
        self.replay = ReplayStore(replay_db)
        self.audit = AuditLedger(audit_db)
        self.server = server
        self.ca_cert = ca_cert
        self.clock = clock
        self.allowed = set(allowed_namespaces)
        self.gateway_identity = gateway_identity

    # ---- read helpers the gateway calls (no mutation authority) ----

    def state(self, namespace, kind, name) -> dict:
        try:
            obj = self.admin.get(GVR[kind], namespace, name)
            return {"present": True, "resource_version": obj["metadata"]["resourceVersion"],
                    "uid": obj["metadata"].get("uid", "")}
        except K8sApiError as e:
            if e.status == 404:
                return {"present": False, "resource_version": None, "uid": None}
            raise

    def dry_run(self, namespace, kind, name, manifest, verb) -> dict:
        gvr = GVR[kind]
        try:
            if verb in ("create", "update"):
                obj = self.admin.apply(gvr, namespace, name, manifest, dry_run=True)
            else:
                obj = self.admin.delete(gvr, namespace, name, dry_run=True)
            return {"ok": True, "predicted_name": obj.get("metadata", {}).get("name")}
        except K8sApiError as e:
            return {"ok": False, "reason": e.reason, "status": str(e.status)}

    def backup_exists(self, ref: str) -> bool:
        try:
            cm = self.admin.get(GVR["ConfigMap"], "protected", "backup-registry")
            return ref in (cm.get("data") or {})
        except K8sApiError:
            return False

    # ---- the sole mutation path ----

    def execute(self, authz_doc: dict) -> dict:
        now = self.clock.now()
        ok, reason = authz.verify_exec_authz(
            self.keyring, authz_doc, now=now, expected_gateway_identity=self.gateway_identity)
        if not ok:
            self._audit("REJECT", authz_doc.get("intent", {}), reason)
            raise BrokerError(reason, "authorization verification failed")

        intent = authz_doc["intent"]
        ah, ph = intent["action_hash"], intent["policy_hash"]

        # independently enforce the broker's OWN trusted policy identity
        if ph != self.active_policy_hash:
            raise self._reject(intent, "E_POLICY_MISMATCH")

        ns, kind, name = intent["namespace"], intent["kind"], intent["name"]
        verb = intent["verb"]
        if ns not in self.allowed:
            raise self._reject(intent, "E_NAMESPACE")
        manifest = intent.get("manifest")

        # defence in depth: re-run semantic checks before any privileged action
        violations = policy_semantic.check({"namespace": ns, "kind": kind, "name": name},
                                           manifest, allowed_namespaces=self.allowed,
                                           backup_exists=self.backup_exists)
        if violations:
            raise self._reject(intent, "E_SEMANTIC:" + violations[0]["check"])

        # destructive: independent Ed25519 approval verification (SoD, quorum, rollback)
        if verb == "delete":
            approvers = set()
            for ap in authz_doc.get("approvals", []):
                if authz.verify_approval(self.keyring, ap, action_hash=ah, policy_hash=ph, now=now):
                    if not self.replay.claim_nonce("approval", ap["nonce"], at=now):
                        raise self._reject(intent, "E_APPROVAL_REPLAY")
                    approvers.add(ap["approver_id"])
            if len(approvers) < 2:
                raise self._reject(intent, "E_APPROVAL_QUORUM")
            if not policy_semantic.rollback_verified(intent.get("rollback_plan"),
                                                     backup_exists=self.backup_exists):
                raise self._reject(intent, "E_ROLLBACK_UNVERIFIED")

        # durable single-use: execution nonce + single commit claim
        if not self.replay.claim_nonce("exec_token", intent["nonce"], at=now):
            raise self._reject(intent, "E_NONCE_REPLAY")
        if not self.replay.claim_commit(ah, at=now):
            raise self._reject(intent, "E_DUPLICATE_COMMIT")

        try:
            result = self._mint_scope_and_write(intent, ns, kind, name, verb, manifest)
        except BrokerError:
            self.replay.release_commit(ah)
            raise
        rh = ref_hashing.domain_digest("EXECUTION_RESULT",
                                       str(sorted(result.items())).encode())
        self.replay.finalize_commit(ah, rh)
        self._audit("COMMIT", intent, "OK", extra={"result_rv": result.get("resource_version")})
        return {"outcome": "COMMITTED", **result}

    def _mint_scope_and_write(self, intent, ns, kind, name, verb, manifest) -> dict:
        gvr = GVR[kind]
        short = ref_hashing.domain_digest("EXECUTION_TOKEN", intent["nonce"].encode())[:12]
        sa = f"cap-{short}"
        verbs = _VERBS[verb]
        # 1. per-action ServiceAccount + minimal Role + RoleBinding
        self.admin.create(GVR["ServiceAccount"], ns, {"apiVersion": "v1",
                          "kind": "ServiceAccount", "metadata": {"name": sa, "namespace": ns}})
        named = [v for v in verbs if v != "create"]
        rules = []
        if named:
            rules.append({"apiGroups": [gvr.group], "resources": [gvr.resource],
                          "resourceNames": [name], "verbs": named})
        if "create" in verbs:
            rules.append({"apiGroups": [gvr.group], "resources": [gvr.resource], "verbs": ["create"]})
        self.admin.create(GVR["Role"], ns, {"apiVersion": "rbac.authorization.k8s.io/v1",
                          "kind": "Role", "metadata": {"name": sa, "namespace": ns}, "rules": rules})
        self.admin.create(GVR["RoleBinding"], ns, {"apiVersion": "rbac.authorization.k8s.io/v1",
                          "kind": "RoleBinding", "metadata": {"name": sa, "namespace": ns},
                          "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": sa},
                          "subjects": [{"kind": "ServiceAccount", "name": sa, "namespace": ns}]})
        tr = self.admin.request_token(ns, sa, audiences=["https://kubernetes.default.svc"],
                                      expiration_seconds=600)
        bearer = tr["status"]["token"]
        scoped = KubeClient(self.server, self.ca_cert, token=bearer)

        try:
            result = self._conditional_write(scoped, gvr, ns, name, verb, manifest, intent)
        finally:
            self._teardown_verified(sa, ns)  # single-use; failure reported, not swallowed
        return result

    def _conditional_write(self, client, gvr, ns, name, verb, manifest, intent) -> dict:
        """Optimistic-concurrency write: rejects if live state moved since approval."""
        approved_rv = intent.get("state_rv")
        present = intent.get("state_present")
        try:
            if verb == "create":
                if present:  # approved as absent but now exists -> collision
                    raise BrokerError("E_STALE_STATE", "resource appeared after approval")
                obj = client.create(gvr, ns, manifest)
            elif verb == "update":
                m = dict(manifest)
                m.setdefault("metadata", {})["resourceVersion"] = approved_rv  # CAS
                obj = client.replace(gvr, ns, name, m)
            else:  # delete
                pre = {"resourceVersion": approved_rv} if approved_rv else None
                obj = client.delete(gvr, ns, name, preconditions=pre)
        except K8sApiError as e:
            if e.status == 409:  # optimistic-concurrency conflict == TOCTOU caught at the write
                raise BrokerError("E_STALE_STATE", "resourceVersion conflict at commit")
            if e.status == 403:
                raise BrokerError("E_SCOPE", "scoped credential denied")
            raise BrokerError("E_WRITE", str(e))
        return {"verb": verb, "kind": gvr.resource, "name": name, "namespace": ns,
                "resource_version": obj.get("metadata", {}).get("resourceVersion", "")}

    def _teardown_verified(self, sa, ns):
        errors = []
        for kind in ("RoleBinding", "Role", "ServiceAccount"):
            try:
                self.admin.delete(GVR[kind], ns, sa)
            except K8sApiError as e:
                if e.status != 404:
                    errors.append(f"{kind}:{e.status}")
        # verify the SA is really gone (revocation confirmed)
        try:
            self.admin.get(GVR["ServiceAccount"], ns, sa)
            errors.append("ServiceAccount:still-present")
        except K8sApiError as e:
            if e.status != 404:
                errors.append(f"verify:{e.status}")
        if errors:
            self._audit("TEARDOWN_FAILURE", {"sa": sa, "namespace": ns}, ",".join(errors))
            raise BrokerError("E_TEARDOWN", f"credential revocation not confirmed: {errors}")

    def _reject(self, intent, code) -> BrokerError:
        self._audit("REJECT", intent, code)
        return BrokerError(code, "broker rejected")

    def _audit(self, kind, intent, detail, extra=None):
        self.audit.append({"event": kind, "action_hash": intent.get("action_hash", ""),
                           "operation": intent.get("operation", ""), "verb": intent.get("verb", ""),
                           "namespace": intent.get("namespace", ""), "name": intent.get("name", ""),
                           "detail": detail, "at": self.clock.now(), **(extra or {})})

    def verify_audit(self):
        return self.audit.verify_against_checkpoint(self.keyring)
