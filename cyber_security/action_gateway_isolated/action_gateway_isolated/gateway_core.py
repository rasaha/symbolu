"""Gateway decision core (no privileged K8s authority, no approver/policy keys).

Computes the action identity through the single shared ``canon`` module (N9) — the
exact same function the broker calls to recompute it (N5) — so there is one framed
hashing implementation, not an ad-hoc string concatenation. Runs the deterministic
policy checks, requests state + a real server-side dry-run from the broker, and —
on ALLOW — builds an Ed25519 execution authorization it signs with the GATEWAY key
only, then hands it to the broker. The agent never sees or forwards the
authorization; decision and execution are one gateway-side transaction, so a
compromised agent cannot interpose a modified action, target, or scope after
approval.
"""

from __future__ import annotations

from . import authz, canon, policy_semantic
from ._core import GVR, ref_hashing
from . import layout
from action_gateway_k8s import mapping


class GatewayCore:
    def __init__(self, *, gateway_sk, keyring, broker, clock, policy_hash, policy_version,
                 gateway_identity, allowed_namespaces=("protected",), token_ttl=300,
                 cluster_id=layout.CLUSTER_ID):
        self.sk = gateway_sk
        self.keyring = keyring
        self.broker = broker
        self.clock = clock
        self.policy_hash = policy_hash
        self.policy_version = policy_version
        self.identity = gateway_identity
        self.allowed = set(allowed_namespaces)
        self.token_ttl = token_ttl
        self.cluster_id = cluster_id
        self._seq = 0

    def handle(self, request: dict) -> dict:
        """Single-transaction: validate -> decide -> dry-run -> authorize -> execute."""
        tool = request.get("tool")
        args = request.get("arguments", {})
        approvals = request.get("approvals", [])
        try:
            spec = mapping.get_spec(tool)
        except Exception:
            return self._deny("E_UNKNOWN_TOOL", tool)
        if spec.read_only:
            return self._read(spec, args)
        try:
            ns, kind, name, manifest = mapping.validate_and_extract(spec, args)
        except Exception as e:
            return self._deny(getattr(e, "code", "E_BAD_ARGS"), str(e))

        # deterministic semantic gate (feeds the decision; broker re-checks)
        violations = policy_semantic.check({"namespace": ns, "kind": kind, "name": name},
                                           manifest, allowed_namespaces=self.allowed,
                                           backup_exists=self.broker.backup_exists)
        if violations:
            return self._deny("E_SEMANTIC:" + violations[0]["check"],
                              [v["check"] for v in violations])

        state = self.broker.state(ns, kind, name)
        gvr = GVR[kind]
        verb = "delete" if spec.verb == "delete" else ("create" if not state["present"] else "update")
        # single shared framed hashing (N9); the broker recomputes these identically (N5)
        state_hash = canon.state_hash(ns, kind, name, state["present"], state["resource_version"])
        action_hash = canon.action_hash(
            cluster=self.cluster_id, namespace=ns, api_group=gvr.group, api_version=gvr.version,
            kind=kind, name=name, verb=verb, manifest=manifest, policy_hash=self.policy_hash,
            state_present=state["present"], state_rv=state["resource_version"])

        # real server-side dry-run via the broker (admin identity, non-mutating)
        dr = self.broker.dry_run(ns, kind, name, manifest, verb)
        if not dr.get("ok"):
            return self._deny("E_DRY_RUN_REJECTED", dr)

        # destructive requires human Ed25519 approvals (verified with PUBLIC keys)
        if spec.verb == "delete":
            valid = [a for a in approvals if authz.verify_approval(
                self.keyring, a, action_hash=action_hash, policy_hash=self.policy_hash,
                now=self.clock.now())]
            distinct = {a["approver_id"] for a in valid}
            if len(distinct) < 2:
                return {"outcome": "ESCALATE_TO_HUMAN", "action_hash": action_hash,
                        "policy_hash": self.policy_hash, "reason": "dual approval required",
                        "executable": False}
            approvals = valid

        # build Ed25519 execution authorization and execute (one transaction).
        # The intent carries EVERY input to canon.action_hash so the broker can
        # recompute the identity independently (N5) rather than trusting the field.
        self._seq += 1
        intent = {
            "action_hash": action_hash, "policy_hash": self.policy_hash,
            "decision_record_hash": ref_hashing.domain_digest("AUDIT_RECORD", action_hash.encode()),
            "operation": spec.operation, "cluster": self.cluster_id,
            "namespace": ns, "api_group": gvr.group, "api_version": gvr.version,
            "kind": kind, "name": name, "verb": verb, "manifest": manifest,
            "manifest_digest": canon.manifest_digest(manifest),
            "state_hash": state_hash, "state_rv": state["resource_version"],
            "state_present": state["present"], "rollback_plan": args.get("rollback_plan"),
            "gateway_identity": self.identity, "expiry": self.clock.plus(self.token_ttl),
            "nonce": f"tok-{action_hash[:10]}-{self._seq}"}
        authz_doc = authz.build_exec_authz(self.sk, intent, approvals)
        try:
            result = self.broker.execute(authz_doc)
        except Exception as e:
            return {"outcome": "DENY", "action_hash": action_hash,
                    "reason_codes": [getattr(e, "code", type(e).__name__)],
                    "message": str(e), "executable": False}
        return {"outcome": "COMMITTED", "action_hash": action_hash, "executable": True, **result}

    def _read(self, spec, args):
        try:
            ns, kind, name, _ = mapping.validate_and_extract(spec, args)
        except Exception as e:
            return self._deny(getattr(e, "code", "E_BAD_ARGS"), str(e))
        if kind == "Secret":
            return self._deny("E_SECRET_EXPORT", "secret read denied")
        st = self.broker.state(ns, kind, name)
        return {"outcome": "ALLOW", "read_only": True, "executable": False,
                "present": st["present"], "resource_version": st["resource_version"]}

    def _deny(self, code, detail=None):
        return {"outcome": "DENY", "reason_codes": [code], "detail": detail, "executable": False}
