"""K8sGateway — bypass-resistant enforcement orchestration against a real cluster.

Reuses the runtime gateway (decisions, tokens, audit, execution lock, TOCTOU
mechanism) and the frozen primitives; adds: a REAL state oracle (so the envelope
current-state hash and the commit-time re-read come from the live cluster),
deterministic admission evidence, real server-side dry-run evidence, exact-action
approval, real Kubernetes execution via a scoped capability, and predicted-versus-
actual convergence checking.
"""

from __future__ import annotations

import tempfile
import threading

from . import cluster as cluster_mod
from . import mapping, policy, simulation
from ._core import (
    Gateway, Metrics, ProtocolAudit, RealClock, ref_errors, ref_hashing, ref_jcs,
)
from .adapter import KubernetesAdapter, _redact
from .broker import KubernetesCredentialBroker
from .errors import (
    BadK8sArgumentError, ClusterUnavailableError, K8sGatewayError,
    UnknownKindError, UnknownNamespaceError,
)
from .kubeclient import GVR, K8sApiError
from action_gateway_mcp.context import RequestContext  # noqa: F401
from action_gateway_mcp.escalation import build_approval

EXECUTABLE = frozenset({"ALLOW", "ALLOW_WITH_CONSTRAINTS"})
_VOLATILE = {"resourceVersion", "uid", "creationTimestamp", "managedFields",
             "generation", "selfLink"}


def _stringify(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return {k: _stringify(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_stringify(x) for x in v]
    return v


def _content_digest(obj: dict) -> str:
    """Digest of an object's durable content (ignoring volatile server fields)."""
    o = dict(obj)
    o.pop("status", None)
    md = {k: v for k, v in (o.get("metadata", {}) or {}).items() if k not in _VOLATILE}
    core = {"kind": o.get("kind"), "metadata": md, "spec": o.get("spec"), "data": o.get("data")}
    return ref_hashing.domain_digest(
        "EXECUTION_RESULT", ref_jcs.canonicalize_str(_stringify(core)).encode("utf-8"))


class K8sStateOracle:
    """Real state oracle: hashes the live resource's resourceVersion (or 'absent').

    Plugged into the runtime gateway so BOTH the submitted envelope's
    current_state_hash and the commit-time TOCTOU re-read reflect live cluster
    state — no mock, no injected assumptions.
    """

    def __init__(self, admin_getter):
        self._admin = admin_getter
        self._ver = {}  # unused (state is live); present for gateway snapshot compatibility

    def _parse(self, target):
        tgt = target[0] if isinstance(target, (list, tuple)) else target
        _, rest = tgt.split("://", 1)
        return rest.split("/", 2)  # ns, kind, name

    def state_hash(self, tool, target):
        ns, kind, name = self._parse(target)
        try:
            obj = self._admin().get(GVR[kind], ns, name)
            token = f"{ns}/{kind}/{name}@{obj.get('metadata', {}).get('resourceVersion', '?')}"
        except K8sApiError as e:
            if e.status == 404:
                token = f"{ns}/{kind}/{name}@absent"
            else:
                raise
        return "sha256:" + ref_hashing.domain_digest("ACTION", token.encode("utf-8"))

    def bump(self, tool, target):  # unused for the real cluster (state changes naturally)
        pass


class K8sGateway:
    def __init__(self, *, allowed_namespaces=("protected",), clock=None,
                 admin_client=None, token_ttl_seconds=300, require_cluster=True):
        self.clock = clock or RealClock()
        self.allowed_namespaces = set(allowed_namespaces)
        self._admin = admin_client
        if require_cluster and not self._cluster_ok():
            raise ClusterUnavailableError("no reachable Kubernetes control plane")
        self.bundle = policy.build_bundle(allowed_namespaces=allowed_namespaces)
        self.broker = KubernetesCredentialBroker(self._admin)
        self.adapter = KubernetesAdapter()
        self.gateway = Gateway(
            sandbox_root=tempfile.mkdtemp(prefix="k8s-gw-"), clock=self.clock,
            broker=self.broker, adapters={"kubernetes": self.adapter},
            token_ttl_seconds=token_ttl_seconds, policy_bundle=self.bundle)
        self.gateway.oracle = K8sStateOracle(self._admin_client)  # real state
        self.audit = ProtocolAudit(self.clock, chain_id="k8s-protocol")
        self.metrics = Metrics()
        self.escalations = {}
        self._meta = {}
        self._seen = set()
        self._seq_wm = {}
        self._lock = threading.RLock()

    # ---- cluster helpers ----

    def _cluster_ok(self):
        try:
            return (self._admin is not None) or cluster_mod.is_available()
        except Exception:  # noqa: BLE001
            return False

    def _admin_client(self):
        return self._admin or cluster_mod.admin_client()

    # ---- guards ----

    def _guard(self, ctx):
        if ctx.request_nonce in self._seen:
            raise K8sGatewayError("protocol request replayed")
        n = ctx.sequence_num()
        if n <= self._seq_wm.get(ctx.correlation_id, -1):
            raise K8sGatewayError("sequence rollback")
        if ctx.identity_conflicts():
            raise K8sGatewayError("declared identity conflicts with authenticated identity")
        self._seen.add(ctx.request_nonce)
        self._seq_wm[ctx.correlation_id] = n

    def _reject(self, code, message, *, action_hash="", metrics=("rejected_bypass_attempts",)):
        for f in metrics:
            self.metrics.inc(f)
        self.metrics.outcome("DENY")
        self.audit.event("rejected", action_hash=action_hash, detail={"code": code})
        return {"outcome": "DENY", "executable": False, "reason_codes": [code],
                "message": message, "execution_token": None, "action_hash": action_hash or None}

    # ---- discovery / read-only ----

    def list_tools(self):
        self.audit.event("tools_list")
        return {"tools": mapping.metadata()}

    def read(self, ctx, tool, args):
        with self._lock:
            self.metrics.inc("requests_total")
            self.audit.event("request_received", detail={"tool": tool, **ctx.identity_record()})
            try:
                self._guard(ctx)
                spec = mapping.get_spec(tool)
            except (UnknownKindError, UnknownNamespaceError) as e:
                return self._reject(e.code, str(e),
                                    metrics=("unknown_tool_rejections", "rejected_bypass_attempts"))
            except K8sGatewayError as e:
                return self._reject("E_K8S_GUARD", str(e))
            if not spec.read_only:
                return self._reject("E_K8S_PHASE", f"{tool} is not read-only")
            try:
                ns, kind, name, _ = mapping.validate_and_extract(spec, args)
            except (UnknownKindError, UnknownNamespaceError, BadK8sArgumentError) as e:
                return self._reject(e.code, str(e))
            if kind == "Secret":
                return self._reject("E_K8S_ADMISSION", "secret export denied")
            obj = self._admin_client().get(GVR[kind], ns, name)
            self.metrics.inc("read_requests")
            self.metrics.outcome("ALLOW")
            self.audit.event("read_served", detail={"tool": tool, "kind": kind, "name": name})
            return {"outcome": "ALLOW", "read_only": True, "executable": False,
                    "execution_token": None,
                    "result": {"kind": obj.get("kind"),
                               "name": obj.get("metadata", {}).get("name"), "namespace": ns,
                               "resourceVersion": obj.get("metadata", {}).get("resourceVersion")}}

    # ---- prepare / evaluate ----

    def prepare(self, ctx, tool, args):
        with self._lock:
            self.metrics.inc("requests_total")
            self.audit.event("request_received", detail={"tool": tool, **ctx.identity_record()})
            try:
                self._guard(ctx)
                spec = mapping.get_spec(tool)
            except (UnknownKindError, UnknownNamespaceError) as e:
                return self._reject(e.code, str(e),
                                    metrics=("unknown_tool_rejections", "rejected_bypass_attempts"))
            except K8sGatewayError as e:
                return self._reject("E_K8S_GUARD", str(e))
            if spec.read_only:
                return self.read(ctx, tool, args)
            try:
                ns, kind, name, manifest = mapping.validate_and_extract(spec, args)
                req = mapping.to_tool_request(spec, args, ctx, current_state_hash="")
            except (UnknownKindError, UnknownNamespaceError, BadK8sArgumentError) as e:
                return self._reject(e.code, str(e))
            sub = self.gateway.submit_action(req)  # oracle sets the real current_state_hash
            rid, ah = sub["request_id"], sub["action_hash"]
            adm_ev, violations = policy.admission_evidence(
                ah, req.args, manifest, allowed_namespaces=self.allowed_namespaces, clock=self.clock)
            rb_ev = policy.rollback_evidence(ah, req.rollback_plan, clock=self.clock)
            self._meta[rid] = {"tool": tool, "operation": spec.operation, "verb": spec.verb,
                               "namespace": ns, "kind": kind, "name": name,
                               "manifest_json": req.args.get("manifest_json"),
                               "admission_ev": adm_ev, "rollback_ev": rb_ev,
                               "violations": violations, "sim_ev": None, "predicted": None,
                               "escalation_id": None, "actual_digest": None,
                               "approver_policy": spec.approver_policy}
            self.audit.event("envelope_constructed", action_hash=ah,
                             detail={"tool": tool, "operation": spec.operation,
                                     "violations": [v["check"] for v in violations]})
            return {"phase": "prepared", "request_id": rid, "action_hash": ah,
                    "operation": spec.operation, "executable": False, "execution_token": None,
                    "admission_compliant": adm_ev is not None, "violations": violations,
                    "current_state_hash": self.gateway.records[rid].envelope["current_state_hash"]}

    def _collected(self, meta):
        return [e for e in (meta["admission_ev"], meta["rollback_ev"], meta["sim_ev"]) if e]

    def evaluate(self, ctx, request_id, *, approvals=None):
        with self._lock:
            self.metrics.inc("requests_total")
            try:
                self._guard(ctx)
            except K8sGatewayError as e:
                return self._reject("E_K8S_GUARD", str(e))
            if request_id not in self._meta:
                return self._reject("E_K8S_UNKNOWN_REQUEST", f"unknown request {request_id}")
            meta = self._meta[request_id]
            ah = self.gateway.records[request_id].action_hash
            self.audit.event("evaluation_requested", action_hash=ah, detail={"request_id": request_id})
            dec = self.gateway.evaluate_action(
                request_id, evidence=self._collected(meta), approvals=approvals or [])
            self.audit.event("decision", action_hash=ah,
                             detail={"outcome": dec["outcome"], "rules": dec["dispositive_rules"]})
            self.metrics.outcome(dec["outcome"])
            esc = meta.get("escalation_id")
            if dec["outcome"] == "ESCALATE_TO_HUMAN" and not esc:
                esc = self._escalate(request_id, meta, dec)
                meta["escalation_id"] = esc
            return self._response(dec, request_id, esc)

    def dry_run(self, ctx, request_id):
        if request_id not in self._meta:
            return self._reject("E_K8S_UNKNOWN_REQUEST", f"unknown request {request_id}")
        meta = self._meta[request_id]
        rec = self.gateway.records[request_id]
        ev, info = simulation.produce(
            self._admin_client(), action_hash=rec.action_hash, env_args=rec.req.args,
            manifest_json=meta["manifest_json"],
            state_hash=rec.envelope["current_state_hash"], verb=meta["verb"], clock=self.clock)
        if ev is None:
            self.audit.event("dry_run_rejected", action_hash=rec.action_hash, detail=info)
            self.metrics.outcome("DENY")
            return {"outcome": "DENY", "executable": False, "request_id": request_id,
                    "reason_codes": ["E_K8S_DRY_RUN_REJECTED"], "dry_run": info,
                    "execution_token": None}
        meta["sim_ev"] = ev
        meta["predicted"] = info["predicted"]
        self.audit.event("dry_run_bound", action_hash=rec.action_hash, detail={"ok": True})
        return self.evaluate(ctx, request_id)

    request_dry_run = dry_run

    # ---- escalation / approval ----

    def _escalate(self, request_id, meta, dec):
        eid = f"esc-{len(self.escalations) + 1}"
        rec = self.gateway.records[request_id]
        self.escalations[eid] = {
            "escalation_id": eid, "request_id": request_id, "action_hash": rec.action_hash,
            "action_summary": {"operation": meta["operation"], "namespace": meta["namespace"],
                               "kind": meta["kind"], "name": meta["name"], "verb": meta["verb"]},
            "dispositive_rules": dec["dispositive_rules"],
            "approval_scope": {"operation": meta["operation"], "target": rec.envelope["target_resource"]},
            "consequence": f"{meta['verb']} {meta['kind']}/{meta['name']} in {meta['namespace']}",
            "required_approver_roles": [meta.get("approver_policy") or "single"],
            "expiry": self.clock.plus(3600), "correlation_id": rec.envelope["correlation_id"],
            "status": "OPEN"}
        self.audit.event("escalated", action_hash=rec.action_hash, detail={"escalation_id": eid})
        return eid

    def list_escalations(self):
        return {"escalations": list(self.escalations.values())}

    def create_test_approval(self, request_id, *, nonce="ap-k8s"):
        meta = self._meta[request_id]
        rec = self.gateway.records[request_id]
        return build_approval(
            action_hash=rec.action_hash, policy_hash=self.gateway.signed_policy["policy_hash"],
            operation=meta["operation"], target=rec.envelope["target_resource"],
            approver_policy=meta.get("approver_policy") or "dual_control",
            issued_at="2026-07-12T13:00:00.000Z", expiration=self.clock.plus(3600), nonce=nonce)

    def attach_approval(self, ctx, request_id, approval):
        self.audit.event("approval_attached",
                         action_hash=self.gateway.records[request_id].action_hash,
                         detail={"request_id": request_id})
        resp = self.evaluate(ctx, request_id, approvals=[approval])
        eid = self._meta.get(request_id, {}).get("escalation_id")
        if eid and resp.get("outcome") in EXECUTABLE and eid in self.escalations:
            self.escalations[eid]["status"] = "APPROVED"
        return resp

    # ---- execution ----

    def execute(self, ctx, request_id, *, observed_state_hash=None):
        return self._commit(ctx, request_id, observed_state_hash=observed_state_hash)

    def _commit(self, ctx, request_id, *, call_envelope=None, observed_state_hash=None,
                requested_permissions=None, active_policy_hash=None):
        with self._lock:
            self.metrics.inc("requests_total")
            try:
                self._guard(ctx)
            except K8sGatewayError as e:
                return self._reject("E_K8S_GUARD", str(e))
            if request_id not in self._meta:
                return self._reject("E_K8S_UNKNOWN_REQUEST", f"unknown request {request_id}")
            meta = self._meta[request_id]
            rec = self.gateway.records[request_id]
            self.audit.event("execution_attempted", action_hash=rec.action_hash,
                             detail={"request_id": request_id})
            if rec.token is None:
                return self._reject("E_NO_EXECUTION_TOKEN",
                                    f"request not executable (state={rec.state})",
                                    action_hash=rec.action_hash)
            try:
                # observed_state_hash=None -> the gateway re-reads via the real oracle
                out = self.gateway.execute_action(
                    request_id, call_envelope=call_envelope,
                    observed_state_hash=observed_state_hash,
                    requested_permissions=requested_permissions,
                    active_policy_hash=active_policy_hash)
            except ref_errors.GateError as e:
                return self._on_reject(e, rec.action_hash)
            except Exception as e:  # noqa: BLE001  (broker/adapter/cluster failures)
                return self._on_reject(e, rec.action_hash)
            self.metrics.inc("executed_actions")
            actual = out["result"].get("object", {})
            meta["actual_digest"] = _content_digest(actual) if actual else None
            self.audit.event("execution_completed", action_hash=rec.action_hash,
                             detail={"result_hash": out["result_hash"]})
            return {"outcome": rec.decision["outcome"], "executable": True,
                    "request_id": request_id, "action_hash": rec.action_hash,
                    "state": out["state"],
                    "result": {k: v for k, v in out["result"].items() if k != "object"},
                    "result_hash": out["result_hash"], "credential_id": out["credential_id"],
                    "resource_version": out["result"].get("resource_version")}

    def check_convergence(self, request_id):
        """Re-read the live object and compare to what was applied (drift detection)."""
        meta = self._meta[request_id]
        try:
            live = self._admin_client().get(GVR[meta["kind"]], meta["namespace"], meta["name"])
        except K8sApiError as e:
            converged = meta["verb"] == "delete" and e.status == 404
            return {"converged": converged, "reason": e.reason}
        live_digest = _content_digest(live)
        applied = meta.get("actual_digest")
        converged = applied is not None and live_digest == applied
        return {"converged": converged, "applied_digest": applied, "live_digest": live_digest,
                "divergence": None if converged else "live object diverged from applied state"}

    def _on_reject(self, exc, action_hash):
        code = getattr(exc, "code", type(exc).__name__)
        field = {"E_NONCE_REPLAY": "token_replays", "E_STALE_STATE": "stale_state_rejections",
                 "E_CREDENTIAL": "capability_replays"}.get(code)
        fields = ("rejected_bypass_attempts",) + ((field,) if field else ())
        return self._reject(code, str(exc), action_hash=action_hash, metrics=fields)

    def _response(self, dec, request_id, escalation_id=None):
        return {"outcome": dec["outcome"], "executable": dec["outcome"] in EXECUTABLE,
                "request_id": request_id, "action_hash": dec["action_hash"],
                "dispositive_rules": dec["dispositive_rules"],
                "reason_codes": [dec["reason"]] if dec.get("reason") else list(dec["dispositive_rules"]),
                "applied_constraints": dec.get("applied_constraints"),
                "escalation_id": escalation_id, "execution_token": None}

    # ---- introspection ----

    def status(self, request_id):
        st = self.gateway.status(request_id)
        st["escalation_id"] = self._meta.get(request_id, {}).get("escalation_id")
        return st

    def audit_dump(self):
        return {"protocol_audit": self.audit.dump(),
                "enforcement_audit": self.gateway.audit_log()}

    def verify_audit(self):
        p = self.audit.verify()
        e = self.gateway.verify_audit()
        both = p["intact"] and e["intact"]
        if not both:
            self.metrics.inc("audit_verification_failures")
        return {"intact": both, "protocol": p, "enforcement": e}

    def metrics_snapshot(self):
        return self.metrics.as_dict()

    # ---- persistence (file-backed CLI) ----

    def snapshot(self):
        return {"gateway": self.gateway.snapshot(), "meta": self._meta,
                "escalations": self.escalations, "metrics": self.metrics.snapshot(),
                "protocol_audit": self.audit.snapshot(), "seen": sorted(self._seen),
                "seq_wm": self._seq_wm, "allowed_namespaces": sorted(self.allowed_namespaces),
                "token_ttl": self.gateway.token_ttl}

    @classmethod
    def restore(cls, snap, *, clock=None):
        obj = cls(allowed_namespaces=tuple(snap["allowed_namespaces"]), clock=clock,
                  token_ttl_seconds=snap.get("token_ttl", 300))
        obj.gateway = Gateway.restore(
            snap["gateway"], clock=obj.clock, broker=obj.broker,
            adapters={"kubernetes": obj.adapter}, policy_bundle=obj.bundle)
        obj.gateway.oracle = K8sStateOracle(obj._admin_client)
        obj.audit.restore(snap["protocol_audit"])
        obj.metrics = Metrics.restore(snap["metrics"])
        obj._meta = dict(snap["meta"])
        obj.escalations = dict(snap["escalations"])
        obj._seen = set(snap["seen"])
        obj._seq_wm = dict(snap["seq_wm"])
        return obj
