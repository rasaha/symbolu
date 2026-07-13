"""MCP-facing enforcement gateway (the protocol boundary).

Wraps the runtime gateway with MCP transport, a canonical mapping registry, a
protocol audit log, an escalation queue, and observational metrics. Enforces the
distinct phases:

  * discovery / read-only  — schemas + non-sensitive metadata, no execution authority
  * evaluation             — build + evaluate an action, never execute it
  * execution              — requires a valid token + broker capability

No handler invokes a tool adapter directly; every side-effecting call goes through
``action_gateway.Gateway`` (token verify -> scoped capability -> adapter -> audit).
A protocol request is never, by itself, execution authority.
"""

from __future__ import annotations

import threading

from . import protocol, registry, simulation
from ._core import Gateway, RealClock, ToolRequest, ref_errors, ref_remediation
from .audit import Metrics, ProtocolAudit
from .context import RequestContext
from .errors import (
    ArgumentError, IdentityMismatchError, McpError, PhaseError,
    ReplayedRequestError, SequenceRollbackError, UnknownToolError,
)
from .escalation import EscalationQueue, build_approval

DENY = protocol.DENY
EXECUTABLE = protocol.EXECUTABLE

# R1.5: the capability that, ON TOP OF an authenticated session, unlocks a privileged
# remediation disclosure mode. A privileged mode is NEVER granted by request alone —
# it requires (a) a transport-authenticated caller and (b) this capability.
_REMEDIATION_CAP = {
    ref_remediation.TRUSTED_PLANNER: "remediation:trusted_planner",
    ref_remediation.HUMAN_ONLY: "remediation:human",
    ref_remediation.FULL: "remediation:full",
}
_REMEDIATION_FIELDS = ("response_schema_version", "all_unmet_conditions", "required_changes",
                       "retryability", "disclosure", "retry_budget")


class McpGateway:
    def __init__(self, *, sandbox_root: str, clock=None, token_ttl_seconds: int = 300):
        self.clock = clock or RealClock()
        self.gateway = Gateway(sandbox_root=sandbox_root, clock=self.clock,
                               token_ttl_seconds=token_ttl_seconds)
        self.broker = self.gateway.broker
        self.audit = ProtocolAudit(self.clock)
        self.escalations = EscalationQueue()
        self.metrics = Metrics()
        self._meta: dict[str, dict] = {}
        self._seen_nonces: set[str] = set()
        self._seq_watermark: dict[str, int] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------- guards

    def _guard_protocol(self, ctx: RequestContext) -> None:
        if ctx.request_nonce in self._seen_nonces:
            raise ReplayedRequestError(f"protocol request nonce reused: {ctx.request_nonce}")
        n = ctx.sequence_num()
        wm = self._seq_watermark.get(ctx.correlation_id, -1)
        if n <= wm:
            raise SequenceRollbackError(f"sequence {n} <= watermark {wm}")
        self._seen_nonces.add(ctx.request_nonce)
        self._seq_watermark[ctx.correlation_id] = n

    def _guard_identity(self, ctx: RequestContext) -> None:
        conflicts = ctx.identity_conflicts()
        if conflicts:
            raise IdentityMismatchError(
                "declared identity conflicts with authenticated identity: "
                + ", ".join(c["field"] for c in conflicts))

    def _reject(self, *, code, message, action_hash="", metrics_fields=(), detail=None):
        for f in metrics_fields:
            self.metrics.inc(f)
        self.metrics.outcome(DENY)
        self.audit.event("rejected", action_hash=action_hash,
                         detail={"code": code, **(detail or {})})
        return {"outcome": DENY, "executable": False, "next_action": "NONE",
                "reason_codes": [code], "message": message, "execution_token": None,
                "action_hash": action_hash or None}

    # ------------------------------------------------------------- helpers

    def _tool_request(self, ctx: RequestContext, spec, args) -> ToolRequest:
        principal = ctx.effective_agent_id()
        return ToolRequest(
            tool=spec.gateway_tool, verb=spec.gateway_verb,
            target=spec.target_builder(args), args=registry.build_arguments(spec, args),
            principal=principal, agent_id=principal, key_id=ctx.agent_key_id,
            delegator=ctx.delegator, delegator_type=ctx.delegator_type,
            objective=f"mcp:{spec.name}", runtime=ctx.agent_runtime,
            model=ctx.model or "claude-opus-4-8", provider=ctx.provider or "anthropic",
            grant="*", reversibility=spec.reversibility,
            permissions=spec.scope_permissions,
            correlation_id=ctx.correlation_id, sequence_id=ctx.sequence_id)

    def _push_escalation(self, ctx, rid, spec, dec) -> str:
        rec = self.gateway.records[rid]
        eid = self.escalations.push(
            request_id=rid, action_hash=dec["action_hash"],
            action_summary={"operation": spec.operation, "tool": spec.name,
                            "target": rec.envelope["target_resource"]},
            dispositive_rules=dec["dispositive_rules"],
            approval_scope={"operation": spec.operation,
                            "target": rec.envelope["target_resource"]},
            consequence=spec.consequence,
            required_approver_roles=[spec.approver_policy or "single"],
            expiry=self.clock.plus(3600), correlation_id=ctx.correlation_id)
        self.audit.event("escalated", action_hash=dec["action_hash"],
                         detail={"escalation_id": eid, "rules": dec["dispositive_rules"]})
        return eid

    def _respond(self, dec, rid, spec, escalation_id=None):
        # forward any advisory remediation fields the gateway attached (R1.5); none by default
        rem = {k: dec[k] for k in _REMEDIATION_FIELDS if k in dec}
        return protocol.decision_response(
            outcome=dec["outcome"], request_id=rid, action_hash=dec["action_hash"],
            dispositive_rules=dec["dispositive_rules"],
            applied_constraints=dec["applied_constraints"], reason=dec["reason"],
            required_evidence=spec.required_evidence, escalation_id=escalation_id,
            remediation=rem or None)

    def _resolve_remediation(self, ctx: RequestContext, requested):
        """Runtime trust resolution. Returns (mode, trusted). OFF/MINIMAL/STANDARD need no
        trust. A privileged mode requires an AUTHENTICATED caller (transport-established
        identity, not the self-declared one) carrying the matching capability; otherwise the
        gateway clamps it down to STANDARD. FULL is never granted by request alone."""
        mode = (requested or "off").upper().replace("-", "_")
        if mode not in ref_remediation.DISCLOSURE_MODES:
            mode = ref_remediation.OFF
        if mode not in _REMEDIATION_CAP:
            return mode, False
        authenticated = ctx.authenticated_agent_id is not None
        caps = set(getattr(ctx, "client_capabilities", []) or [])
        need = _REMEDIATION_CAP[mode]
        trusted = authenticated and (need in caps
                                     or _REMEDIATION_CAP[ref_remediation.FULL] in caps)
        return mode, trusted

    # ------------------------------------------------------------- discovery

    def list_tools(self) -> dict:
        self.audit.event("tools_list")
        return {"tools": registry.metadata()}

    # ------------------------------------------------------------- read-only phase

    def read(self, ctx: RequestContext, tool: str, args: dict) -> dict:
        with self._lock:
            self.metrics.inc("requests_total")
            self.audit.event("request_received", detail={"tool": tool, **ctx.identity_record()})
            try:
                self._guard_protocol(ctx)
                self._guard_identity(ctx)
                spec = registry.get_spec(tool)
            except (ReplayedRequestError, SequenceRollbackError) as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("rejected_bypass_attempts",))
            except IdentityMismatchError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("identity_rejections", "rejected_bypass_attempts"))
            except UnknownToolError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("unknown_tool_rejections", "rejected_bypass_attempts"))
            if not spec.read_only:
                return self._reject(code="E_MCP_PHASE",
                                    message=f"{tool} is not a read-only tool; use evaluate")
            return self._read(ctx, spec, args)

    def _read(self, ctx, spec, args) -> dict:
        from . import readonly
        try:
            registry.validate_arguments(spec, args)
        except ArgumentError as e:
            return self._reject(code=e.code, message=str(e),
                                metrics_fields=("rejected_bypass_attempts",))
        data = readonly.HANDLERS[spec.name](args)
        self.metrics.inc("read_requests")
        self.metrics.outcome("ALLOW")
        self.audit.event("read_only_served", detail={"tool": spec.name})
        return {"outcome": "ALLOW", "phase": "read_only", "executable": False,
                "read_only": True, "execution_token": None, "result": data}

    # ------------------------------------------------------------- prepare phase

    def prepare(self, ctx: RequestContext, tool: str, args: dict) -> dict:
        """Construct + hash an action (submit) WITHOUT evaluating or minting a token.

        Returns the action_hash so the client can bind required evidence/simulation
        before evaluation. Read-only tools are served immediately (no request handle).
        """
        with self._lock:
            self.metrics.inc("requests_total")
            self.audit.event("request_received", detail={"tool": tool, **ctx.identity_record()})
            try:
                self._guard_protocol(ctx)
                self._guard_identity(ctx)
                spec = registry.get_spec(tool)
            except (ReplayedRequestError, SequenceRollbackError) as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("rejected_bypass_attempts",))
            except IdentityMismatchError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("identity_rejections", "rejected_bypass_attempts"))
            except UnknownToolError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("unknown_tool_rejections", "rejected_bypass_attempts"))
            if spec.read_only:
                return self._read(ctx, spec, args)
            try:
                registry.validate_arguments(spec, args)
            except ArgumentError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("rejected_bypass_attempts",))

            req = self._tool_request(ctx, spec, args)
            sub = self.gateway.submit_action(req)
            rid, ah = sub["request_id"], sub["action_hash"]
            self._meta[rid] = {"tool": tool, "sim_kind": spec.simulation_kind,
                               "approver_policy": spec.approver_policy,
                               "operation": spec.operation, "escalation_id": None,
                               "auto_evidence": tuple(spec.auto_evidence),
                               "auto_applied": False, "identity": ctx.identity_record()}
            self.audit.event("envelope_constructed", action_hash=ah,
                             detail={"tool": tool, "operation": spec.operation})
            return {"phase": "prepared", "request_id": rid, "action_hash": ah,
                    "operation": spec.operation, "executable": False,
                    "execution_token": None,
                    "required_evidence": list(spec.required_evidence),
                    "simulation_required": spec.simulation_required,
                    "simulation_kind": spec.simulation_kind,
                    "approver_policy": spec.approver_policy}

    # ------------------------------------------------------------- evaluation phase

    def evaluate(self, ctx: RequestContext, request_id: str, *,
                 evidence=None, approvals=None, remediation_mode="off") -> dict:
        """Evaluate a prepared request through the frozen gate. Never executes.

        Re-callable: supply more evidence/approvals to advance a PENDING request.
        Mints an execution token in the gateway only on ALLOW / ALLOW_WITH_CONSTRAINTS.

        ``remediation_mode`` (R1.5, default ``"off"``) requests optional advisory remediation
        metadata; privileged modes are gated by the authenticated caller context (see
        ``_resolve_remediation``). Default OFF keeps the response byte-identical.
        """
        with self._lock:
            self.metrics.inc("requests_total")
            try:
                self._guard_protocol(ctx)
                self._guard_identity(ctx)
            except McpError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("rejected_bypass_attempts",))
            if request_id not in self._meta:
                return self._reject(code="E_MCP_UNKNOWN_REQUEST",
                                    message=f"unknown request {request_id}")
            meta = self._meta[request_id]
            spec = registry.get_spec(meta["tool"])
            rec = self.gateway.records[request_id]
            ah = rec.action_hash
            ev = list(evidence or [])
            if not meta["auto_applied"] and meta["auto_evidence"]:
                for kind in meta["auto_evidence"]:  # build provenance from the registry/CI
                    ev.append(simulation.build_provenance(kind, action_hash=ah, clock=self.clock))
                    self.audit.event("evidence_attached", action_hash=ah, detail={"kind": kind})
                meta["auto_applied"] = True
            self.audit.event("evaluation_requested", action_hash=ah,
                             detail={"request_id": request_id})
            rmode, rtrusted = self._resolve_remediation(ctx, remediation_mode)
            dec = self.gateway.evaluate_action(
                request_id, evidence=ev, approvals=approvals or [],
                remediation_mode=rmode, remediation_trusted=rtrusted)
            self.audit.event("decision", action_hash=ah,
                             detail={"outcome": dec["outcome"], "rules": dec["dispositive_rules"]})
            self.metrics.outcome(dec["outcome"])
            esc_id = meta.get("escalation_id")
            if dec["outcome"] == protocol.ESCALATE_TO_HUMAN and not esc_id:
                esc_id = self._push_escalation(ctx, request_id, spec, dec)
                meta["escalation_id"] = esc_id
            return self._respond(dec, request_id, spec, esc_id)

    def provide_evidence(self, ctx, request_id, evidence) -> dict:
        return self.evaluate(ctx, request_id, evidence=evidence)

    def simulate(self, ctx, request_id, *, fidelity="HIGH", inputs=None) -> dict:
        """Produce bound simulation evidence and re-evaluate (Terraform plan /
        Kubernetes dry-run / IAM delta) — never a bare ``safe: true``."""
        if request_id not in self._meta:
            return self._reject(code="E_MCP_UNKNOWN_REQUEST",
                                message=f"unknown request {request_id}")
        meta = self._meta[request_id]
        if not meta.get("sim_kind"):
            return self._reject(code="E_MCP_NO_SIMULATION",
                                message=f"{meta['tool']} declares no simulation")
        rec = self.gateway.records[request_id]
        ev = simulation.produce(
            meta["sim_kind"], action_hash=rec.action_hash,
            state_hash=rec.envelope["current_state_hash"], clock=self.clock,
            inputs=inputs or dict(rec.req.args), fidelity=fidelity)
        self.audit.event("simulation_produced", action_hash=rec.action_hash,
                         detail={"kind": meta["sim_kind"], "fidelity": fidelity})
        return self.evaluate(ctx, request_id, evidence=[ev])

    # ------------------------------------------------------------- escalation / approval

    def list_escalations(self) -> dict:
        return {"escalations": self.escalations.list()}

    def create_test_approval(self, request_id, *, nonce="ap-mcp") -> dict:
        meta = self._meta[request_id]
        rec = self.gateway.records[request_id]
        return build_approval(
            action_hash=rec.action_hash, policy_hash=self.gateway.signed_policy["policy_hash"],
            operation=meta["operation"], target=rec.envelope["target_resource"],
            approver_policy=meta.get("approver_policy") or "dual_control",
            issued_at="2026-07-12T13:00:00.000Z", expiration=self.clock.plus(3600),
            nonce=nonce, clock=self.clock)

    def attach_approval(self, ctx, request_id, approval) -> dict:
        self.audit.event("approval_attached",
                         action_hash=self.gateway.records[request_id].action_hash
                         if request_id in self._meta else "",
                         detail={"request_id": request_id})
        resp = self.evaluate(ctx, request_id, approvals=[approval])
        eid = self._meta.get(request_id, {}).get("escalation_id")
        if eid and resp.get("outcome") in EXECUTABLE:
            self.escalations.close(eid)
        return resp

    # ------------------------------------------------------------- execution phase

    def _enforce_constraints(self, rec) -> None:
        """Dual enforcement: the token must carry exactly the decided constraints
        (constraints are bound into execution authority, not merely returned)."""
        dec_constraints = rec.decision.get("applied_constraints") or {}
        tok_constraints = rec.token["payload"]["constraints"] if rec.token else {}
        if tok_constraints != dec_constraints:
            raise McpError("constraint binding mismatch between decision and token")

    def _on_exec_reject(self, exc, action_hash) -> dict:
        code = getattr(exc, "code", type(exc).__name__)
        field = {"E_NONCE_REPLAY": "token_replays", "E_STALE_STATE": "stale_state_rejections"}.get(code)
        if code == "E_CREDENTIAL" and "already used" in str(exc):
            field = "capability_replays"
        fields = ("rejected_bypass_attempts",) + ((field,) if field else ())
        return self._reject(code=code, message=str(exc), action_hash=action_hash,
                            metrics_fields=fields)

    def execute(self, ctx, request_id, *, observed_state_hash=None) -> dict:
        return self._commit(ctx, request_id, observed_state_hash=observed_state_hash)

    def _commit(self, ctx, request_id, *, call_envelope=None, observed_state_hash=None,
                requested_permissions=None, active_policy_hash=None) -> dict:
        """Single execution path (public execute passes no adversarial overrides).

        The optional overrides model a tampering client and can only cause
        rejection — never a bypass. They are used by the red-team demonstrations.
        """
        with self._lock:
            self.metrics.inc("requests_total")
            try:
                self._guard_protocol(ctx)
                self._guard_identity(ctx)
            except McpError as e:
                return self._reject(code=e.code, message=str(e),
                                    metrics_fields=("rejected_bypass_attempts",))
            if request_id not in self._meta:
                return self._reject(code="E_MCP_UNKNOWN_REQUEST",
                                    message=f"unknown request {request_id}")
            rec = self.gateway.records[request_id]
            self.audit.event("execution_attempted", action_hash=rec.action_hash,
                             detail={"request_id": request_id})
            if rec.token is None:
                return self._reject(code="E_NO_EXECUTION_TOKEN", action_hash=rec.action_hash,
                                    message=f"request {request_id} is not executable "
                                            f"(state={rec.state})")
            try:
                self._enforce_constraints(rec)
                out = self.gateway.execute_action(
                    request_id, call_envelope=call_envelope,
                    observed_state_hash=observed_state_hash,
                    requested_permissions=requested_permissions,
                    active_policy_hash=active_policy_hash)
            except (ref_errors.GateError, McpError) as e:
                return self._on_exec_reject(e, rec.action_hash)
            except Exception as e:  # gateway errors (credential, illegal state, ...)
                return self._on_exec_reject(e, rec.action_hash)
            self.metrics.inc("executed_actions")
            self.audit.event("execution_completed", action_hash=rec.action_hash,
                             detail={"result_hash": out["result_hash"]})
            return {"outcome": rec.decision["outcome"], "executable": True,
                    "request_id": request_id, "action_hash": rec.action_hash,
                    "state": out["state"], "result": out["result"],
                    "result_hash": out["result_hash"], "credential_id": out["credential_id"],
                    "applied_constraints": rec.decision.get("applied_constraints")}

    # ------------------------------------------------------------- introspection

    def status(self, request_id) -> dict:
        st = self.gateway.status(request_id)
        st["escalation_id"] = self._meta.get(request_id, {}).get("escalation_id")
        return st

    def audit_dump(self) -> dict:
        return {"protocol_audit": self.audit.dump(),
                "enforcement_audit": self.gateway.audit_log()}

    def verify_audit(self) -> dict:
        p = self.audit.verify()
        e = self.gateway.verify_audit()
        both = p["intact"] and e["intact"]
        if not both:
            self.metrics.inc("audit_verification_failures")
        return {"intact": both, "protocol": p, "enforcement": e}

    def metrics_snapshot(self) -> dict:
        return self.metrics.as_dict()

    # ------------------------------------------------------------- persistence

    def snapshot(self) -> dict:
        return {"gateway": self.gateway.snapshot(), "meta": self._meta,
                "seen_nonces": sorted(self._seen_nonces),
                "seq_watermark": self._seq_watermark,
                "escalations": self.escalations.snapshot(),
                "metrics": self.metrics.snapshot(),
                "protocol_audit": self.audit.snapshot()}

    @classmethod
    def restore(cls, snap, *, clock=None):
        mcp = cls.__new__(cls)
        mcp.clock = clock or RealClock()
        mcp.gateway = Gateway.restore(snap["gateway"], clock=mcp.clock)
        mcp.broker = mcp.gateway.broker
        mcp.audit = ProtocolAudit(mcp.clock)
        mcp.audit.restore(snap["protocol_audit"])
        mcp.escalations = EscalationQueue()
        mcp.escalations.restore(snap["escalations"])
        mcp.metrics = Metrics.restore(snap["metrics"])
        mcp._meta = dict(snap["meta"])
        mcp._seen_nonces = set(snap["seen_nonces"])
        mcp._seq_watermark = dict(snap["seq_watermark"])
        mcp._lock = threading.RLock()
        return mcp
