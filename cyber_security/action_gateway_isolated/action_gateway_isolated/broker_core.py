"""Credential broker / execution service — the ONLY holder of privileged K8s authority.

Verifies asymmetric authorization independently, INDEPENDENTLY RECOMPUTES the
action identity (N5) instead of trusting the gateway's asserted hash, claims
durable single-use nonces, mints a per-action resource/verb-scoped short-lived
credential, performs a CONDITIONAL (optimistic-concurrency) write that closes the
commit-time TOCTOU race, then — as a SEPARATE, TRANSACTIONAL step — atomically
finalizes the commit and appends its audit record before verifying teardown. A
teardown that does not confirm is recorded in a durable orphan ledger and
reconciled later (N2); it never releases the commit or loses the audit (N3). It
exposes no bearer credential to the gateway/agent.
"""

from __future__ import annotations

import copy

from . import authz, canon, layout, policy_semantic
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
                 gateway_identity, cluster_id=layout.CLUSTER_ID):
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
        self.cluster_id = cluster_id
        # test-only fault injection: force the single-use teardown to fail so the
        # durable orphan ledger + reconciler (N2) can be exercised end to end.
        self._teardown_fault = False
        self._last_scope = None  # the most recently minted RBAC scope (A16 inspection)

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
        if kind not in GVR:
            raise self._reject(intent, "E_UNKNOWN_KIND")
        if verb not in _VERBS:
            raise self._reject(intent, "E_UNKNOWN_VERB")
        manifest = intent.get("manifest")

        # N5: INDEPENDENT RECOMPUTATION. Trust nothing the gateway asserted about the
        # action's identity. Recompute the manifest digest and the action hash from
        # first principles using the broker's OWN trusted cluster id, GVR table, and
        # active policy hash. A mismatch means the signed intent's identity does not
        # match its contents (target, manifest, namespace, or policy) -> fatal.
        self._verify_action_identity(intent, ns, kind, name, verb, manifest)

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

        # privileged write. A BrokerError here is raised BEFORE any mutation (the
        # write itself is the last thing that can fail), so the commit claim is safe
        # to release; the minted RBAC is torn down inside _mint_and_write on failure.
        try:
            result, sa = self._mint_and_write(intent, ns, kind, name, verb, manifest)
        except BrokerError:
            self.replay.release_commit(ah)
            raise

        # The mutation is now DURABLE. Finalize the commit and append its audit
        # record atomically (N3) BEFORE teardown, so a successful execution can never
        # silently lose its commit record or its audit trail. release_commit can no
        # longer touch this action (result_hash is set).
        rh = ref_hashing.domain_digest("EXECUTION_RESULT", str(sorted(result.items())).encode())
        self._finalize_and_audit(ah, rh, intent, result)

        # Teardown of the single-use credential is a SEPARATE durable step. If it does
        # not confirm, the residual RBAC is recorded in the durable orphan ledger and
        # audited for the reconciler (N2) — never swallowed, never lost.
        ok_td, detail = self._teardown(sa, ns)
        if not ok_td:
            self.replay.record_orphan(sa, ns, at=now, action_hash=ah, detail=detail)
            self._audit("TEARDOWN_FAILURE", intent, detail, extra={"orphan_sa": sa})
        return {"outcome": "COMMITTED", "teardown": "confirmed" if ok_td else "orphaned", **result}

    def _verify_action_identity(self, intent, ns, kind, name, verb, manifest) -> None:
        """N5: recompute the identity independently; any mismatch is fatal."""
        gvr = GVR[kind]
        if canon.manifest_digest(manifest) != intent.get("manifest_digest"):
            raise self._reject(intent, "E_MANIFEST_DIGEST_MISMATCH")
        recomputed = canon.action_hash(
            cluster=self.cluster_id, namespace=ns, api_group=gvr.group, api_version=gvr.version,
            kind=kind, name=name, verb=verb, manifest=manifest,
            policy_hash=self.active_policy_hash,
            state_present=intent.get("state_present"), state_rv=intent.get("state_rv"))
        if recomputed != intent.get("action_hash"):
            raise self._reject(intent, "E_ACTION_HASH_MISMATCH")
        # the gateway must not have asserted a different cluster/group/version either
        if intent.get("cluster") not in (None, self.cluster_id):
            raise self._reject(intent, "E_CLUSTER_MISMATCH")
        if intent.get("api_group") not in (None, gvr.group) or \
           intent.get("api_version") not in (None, gvr.version):
            raise self._reject(intent, "E_GVR_MISMATCH")

    def _finalize_and_audit(self, ah, rh, intent, result) -> None:
        """Append the COMMIT audit record, then link it to the finalized commit so
        commit/audit divergence is deterministically detectable (N3)."""
        seq, _ = self.audit.append_record(
            {"event": "COMMIT", "action_hash": ah, "operation": intent.get("operation", ""),
             "verb": intent.get("verb", ""), "namespace": intent.get("namespace", ""),
             "name": intent.get("name", ""), "detail": "OK",
             "result_rv": result.get("resource_version"), "at": self.clock.now()})
        self.replay.finalize_commit(ah, rh, audit_seq=seq)

    def _mint_and_write(self, intent, ns, kind, name, verb, manifest):
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
        self._last_scope = {"namespace": ns, "resource": gvr.resource, "name": name,
                            "verbs": verbs, "rules": rules}  # inspectable minted scope (A16)
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
        except BrokerError:
            # nothing was mutated; tear the just-minted RBAC down. If teardown itself
            # fails, record the orphan durably so the reconciler cleans it (N2).
            ok_td, detail = self._teardown(sa, ns)
            if not ok_td:
                self.replay.record_orphan(sa, ns, at=self.clock.now(),
                                          action_hash=intent.get("action_hash", ""), detail=detail)
                self._audit("TEARDOWN_FAILURE", intent, detail, extra={"orphan_sa": sa})
            raise
        return result, sa

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
                m = copy.deepcopy(manifest)  # never mutate the signed intent's manifest
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

    def _teardown(self, sa, ns):
        """Delete the minted RBAC and VERIFY the ServiceAccount is gone.

        Returns ``(ok, detail)`` and NEVER raises or swallows — the caller decides
        whether a non-confirmation becomes a durable orphan. ``_teardown_fault`` is a
        test-only switch that skips the deletes so a genuine residual is produced.
        """
        errors = []
        for kind in ("RoleBinding", "Role", "ServiceAccount"):
            if self._teardown_fault:
                errors.append(f"{kind}:fault-injected-skip")
                continue
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
            return False, ",".join(errors)
        return True, "confirmed"

    # ---- reconciliation: durable orphan drain + commit/audit divergence (N2/N3) ----

    def reconcile(self) -> dict:
        """Idempotent recovery: drain the orphan ledger (delete + verify each residual
        credential) and detect any commit/audit divergence. Safe to run repeatedly."""
        now = self.clock.now()
        reconciled, still_open = [], []
        for o in self.replay.open_orphans():
            ok, detail = self._teardown(o["sa"], o["namespace"])
            if ok:
                self.replay.resolve_orphan(o["sa"], o["namespace"], at=now)
                self._audit("ORPHAN_RECONCILED", {"namespace": o["namespace"],
                            "name": o["sa"], "action_hash": o.get("action_hash", "")}, "resolved")
                reconciled.append(o["sa"])
            else:
                still_open.append({"sa": o["sa"], "namespace": o["namespace"], "detail": detail})
        return {"reconciled": reconciled, "still_open": still_open,
                "divergence": self.detect_divergence()}

    def detect_divergence(self) -> list:
        """Deterministically detect commit<->audit divergence (N3):
          * a finalized commit whose linked COMMIT audit record is missing;
          * a COMMIT audit record with no finalized commit.
        An intact system returns []."""
        problems = []
        audit_commits = self.audit.event_action_hashes("COMMIT")
        for fc in self.replay.finalized_commits():
            seqs = audit_commits.get(fc["action_hash"], [])
            if not seqs or fc["audit_seq"] not in seqs:
                problems.append({"type": "commit_without_audit",
                                 "action_hash": fc["action_hash"]})
        for ah in audit_commits:
            rec = self.replay.commit_record(ah)
            if rec is None or rec["result_hash"] is None:
                problems.append({"type": "audit_without_commit", "action_hash": ah})
        return problems

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
