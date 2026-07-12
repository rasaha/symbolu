"""The runtime enforcement gateway.

Sits between an autonomous agent and external tools. Every execution follows the
frozen pipeline (ACTION_GATE_SPECIFICATION.md / ROADMAP.md):

    receive -> validate -> canonicalize -> hash -> evaluate -> mint token
            -> issue scoped credential -> invoke adapter -> audit -> return

Invariants enforced here:
  * The gate is the ONLY authority on admissibility (``gate.evaluate``); the
    gateway records and enforces its decision, never overrides it.
  * A tool executes ONLY when a valid, unexpired, unreplayed execution token
    authorizes *this exact* action, and ONLY via a broker-minted scoped
    credential. There is no code path from an agent request to an adapter that
    skips evaluation + token verification.
  * Every decision, execution, and result is appended to a tamper-evident audit
    chain that is re-verified after every append.
"""

from __future__ import annotations

import dataclasses
import hashlib
import threading
from dataclasses import dataclass, field

from . import state as S
from ._ref import audit, gate, hashing, jcs, policy, projection, schema, token
from ._ref import errors as ref_errors
from .adapters import default_adapters
from .broker import MockCredentialBroker
from .clock import RealClock
from .errors import (
    GatewayError, IllegalStateError, NoExecutionTokenError, UnknownRequestError,
    UnknownToolError,
)
from .mapping import ToolRequest, build_envelope, needed_permission


class MockStateOracle:
    """Deterministic stand-in for a live infrastructure state oracle.

    Returns a ``sha256:<hex>`` state hash per (tool, target). ``bump`` changes the
    observed state so a TOCTOU divergence between approval-time and commit-time
    can be demonstrated. NOT a real state source (out of scope).
    """

    def __init__(self):
        self._ver: dict[str, int] = {}

    def _key(self, tool: str, target) -> str:
        return f"{tool}:{'|'.join(target)}"

    def state_hash(self, tool: str, target) -> str:
        k = self._key(tool, target)
        v = self._ver.get(k, 0)
        digest = hashlib.sha256(f"{k}#v{v}".encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def bump(self, tool: str, target) -> None:
        k = self._key(tool, target)
        self._ver[k] = self._ver.get(k, 0) + 1


@dataclass
class Record:
    request_id: str
    req: ToolRequest
    envelope: dict
    action_hash: str
    needed_permission: str
    state: str = S.PENDING
    decision: dict | None = None
    token: dict | None = None
    token_nonce: str | None = None
    evidence: list = field(default_factory=list)
    approvals: list = field(default_factory=list)
    results: list = field(default_factory=list)
    audit_hashes: list = field(default_factory=list)


class Gateway:
    def __init__(self, *, sandbox_root: str, clock=None, broker=None,
                 adapters=None, token_ttl_seconds: int = 300):
        self.clock = clock or RealClock()
        self.broker = broker or MockCredentialBroker()
        self.adapters = adapters or default_adapters(sandbox_root)
        self.token_ttl = token_ttl_seconds
        self._bundle = policy.build_bundle()
        self.signed_policy = policy.sign_policy(self._bundle)
        self.policy_version = policy.policy_version(self._bundle)
        self.sandbox_root = sandbox_root
        self.oracle = MockStateOracle()
        self.chain = audit.AuditChain("gateway-session")
        self.records: dict[str, Record] = {}
        self._spent_nonces: set[str] = set()
        self._id_n = 0
        self._nonce_n = 0
        # serializes evaluate/execute so a token nonce can be reserved atomically;
        # guarantees at most one commit under parallel duplicate execution.
        self._lock = threading.RLock()

    # ---------------------------------------------------------------- helpers

    def _get(self, request_id: str) -> Record:
        rec = self.records.get(request_id)
        if rec is None:
            raise UnknownRequestError(request_id)
        return rec

    def _append_audit(self, rec: Record, *, decision: str, action_hash: str,
                      policy_hash: str, dispositive_rules, applied_constraints,
                      evidence_hashes, approval_hashes, stage: str,
                      execution_token_hash=None, execution_result_hash=None) -> str:
        record = audit.build_audit_record(
            action_hash=action_hash or "", decision=decision,
            dispositive_rules=dispositive_rules or [], policy_hash=policy_hash or "",
            evidence_hashes=evidence_hashes, approval_hashes=approval_hashes,
            applied_constraints=applied_constraints,
            timestamps={stage: self.clock.now()},
            execution_token_hash=execution_token_hash,
            execution_result_hash=execution_result_hash)
        self.chain.append(record)
        if not self.chain.verify():  # re-verify after every append
            raise GatewayError("audit chain verification failed after append")
        rec.audit_hashes.append(record["audit_record_hash"])
        return record["audit_record_hash"]

    def _transition(self, rec: Record, dst: str) -> None:
        if rec.state == dst:
            return
        if not S.can_transition(rec.state, dst):
            raise IllegalStateError(f"{rec.state} -> {dst}")
        rec.state = dst

    # ---------------------------------------------------------------- API: submit

    def submit_action(self, req: ToolRequest) -> dict:
        """Receive -> validate -> canonicalize -> hash. Stores a PENDING record."""
        if req.tool not in self.adapters:
            raise UnknownToolError(req.tool)
        state_hash = self.oracle.state_hash(req.tool, req.target)
        env = build_envelope(req, clock=self.clock, policy_version=self.policy_version,
                             current_state_hash=state_hash)
        # canonicalize + hash via the frozen harness (also structurally exercises it)
        action_hash = projection.action_hash(env)
        self._id_n += 1
        rid = f"req-{self._id_n}"
        rec = Record(request_id=rid, req=req, envelope=env, action_hash=action_hash,
                     needed_permission=needed_permission(req.tool, req.verb))
        self.records[rid] = rec
        return {"request_id": rid, "action_hash": action_hash, "state": rec.state,
                "operation": env["operation"]}

    # ---------------------------------------------------------------- API: evaluate

    def evaluate_action(self, request_id: str, *, evidence=None, approvals=None) -> dict:
        with self._lock:
            return self._evaluate_locked(request_id, evidence=evidence, approvals=approvals)

    def _evaluate_locked(self, request_id: str, *, evidence=None, approvals=None) -> dict:
        """Invoke the frozen gate; record + enforce its decision. Mints a token on ALLOW."""
        rec = self._get(request_id)
        if S.is_terminal(rec.state):
            raise IllegalStateError(f"cannot evaluate terminal request in {rec.state}")
        if evidence:
            rec.evidence.extend(evidence)
        if approvals:
            rec.approvals.extend(approvals)

        now = self.clock.now()
        decision = gate.evaluate(
            rec.envelope, self.signed_policy, evidence=rec.evidence,
            approvals=rec.approvals, now=now, used_nonces=self._spent_nonces)
        rec.decision = decision

        ah = decision.get("action_hash") or rec.action_hash
        ph = decision.get("policy_hash") or self.signed_policy["policy_hash"]
        dec_hash = self._append_audit(
            rec, decision=decision["outcome"], action_hash=ah, policy_hash=ph,
            dispositive_rules=decision["dispositive_rules"],
            applied_constraints=decision.get("applied_constraints"),
            evidence_hashes=[e["evidence_hash"] for e in rec.evidence],
            approval_hashes=[a["approval_hash"] for a in rec.approvals],
            stage="decided")

        new_state = S.OUTCOME_TO_STATE[decision["outcome"]]
        self._transition(rec, new_state)

        if new_state == S.APPROVED:
            self._nonce_n += 1
            nonce = f"tok-{self._nonce_n}"
            tok = token.build_token(
                action_hash=rec.action_hash,
                permitted_operation=rec.envelope["operation"],
                permitted_target=rec.envelope["target_resource"],
                credential_scope=rec.envelope["credential_scope"],
                constraints=decision.get("applied_constraints") or {},
                expiration=self.clock.plus(self.token_ttl), nonce=nonce,
                policy_hash=self.signed_policy["policy_hash"],
                decision_record_hash=dec_hash)
            rec.token, rec.token_nonce = tok, nonce
        else:
            rec.token, rec.token_nonce = None, None

        return {"request_id": request_id, "outcome": decision["outcome"],
                "state": rec.state, "dispositive_rules": decision["dispositive_rules"],
                "applied_constraints": decision.get("applied_constraints"),
                "action_hash": rec.action_hash,
                "token_hash": rec.token["token_hash"] if rec.token else None,
                "reason": decision.get("reason", "")}

    # ---------------------------------------------------------------- API: execute

    def execute_action(self, request_id: str, *, call_envelope=None,
                       observed_state_hash=None, requested_permissions=None,
                       active_policy_hash=None, require_reeval: bool = True) -> dict:
        with self._lock:  # atomic verify+reserve+commit -> at most one commit
            return self._execute_locked(
                request_id, call_envelope=call_envelope,
                observed_state_hash=observed_state_hash,
                requested_permissions=requested_permissions,
                active_policy_hash=active_policy_hash, require_reeval=require_reeval)

    def _execute_locked(self, request_id: str, *, call_envelope=None,
                        observed_state_hash=None, requested_permissions=None,
                        active_policy_hash=None, require_reeval: bool = True) -> dict:
        """Verify the execution token, issue a scoped credential, invoke the adapter.

        No token -> no execution. The token is verified against the *actual* call
        envelope, so any post-approval modification, replay, expiry, scope change,
        policy change, or TOCTOU state drift is rejected before the adapter runs.
        """
        rec = self._get(request_id)
        if rec.token is None:
            raise NoExecutionTokenError(
                f"request {request_id} has no execution token (state={rec.state})")

        env = call_envelope if call_envelope is not None else rec.envelope
        now = self.clock.now()
        state_now = observed_state_hash if observed_state_hash is not None \
            else self.oracle.state_hash(rec.req.tool, rec.req.target)
        active_ph = active_policy_hash or self.signed_policy["policy_hash"]

        # --- enforcement: token must authorize THIS call (raises on any violation)
        try:
            token.verify_token(
                rec.token, env, active_policy_hash=active_ph, now=now,
                used_nonces=self._spent_nonces, require_reeval=require_reeval,
                current_state_hash=state_now)
        except ref_errors.ExpiredError:
            self._transition(rec, S.EXPIRED)
            self._append_audit(
                rec, decision="EXECUTION_DENIED:E_EXPIRED", action_hash=rec.action_hash,
                policy_hash=active_ph, dispositive_rules=["TOKEN_EXPIRED"],
                applied_constraints=None, evidence_hashes=[], approval_hashes=[],
                stage="rejected", execution_token_hash=rec.token["token_hash"])
            raise
        except ref_errors.GateError as exc:
            self._append_audit(
                rec, decision=f"EXECUTION_DENIED:{exc.code}", action_hash=rec.action_hash,
                policy_hash=active_ph, dispositive_rules=[exc.code],
                applied_constraints=None, evidence_hashes=[], approval_hashes=[],
                stage="rejected", execution_token_hash=rec.token["token_hash"])
            raise

        if rec.state != S.APPROVED:  # defensive: only an APPROVED request may run
            raise IllegalStateError(f"cannot execute in state {rec.state}")

        self._transition(rec, S.EXECUTING)
        try:
            # scoped, short-lived capability — the only way an adapter gets to run
            cred = self.broker.issue(
                token=rec.token,
                requested_permissions=requested_permissions or [rec.needed_permission],
                principal=rec.envelope["credential_scope"]["principal"], now=now)
            adapter = self.adapters[rec.req.tool]
            result = adapter.execute(rec.req, cred, broker=self.broker, now=now)
        except Exception as exc:
            self._transition(rec, S.FAILED)
            self._append_audit(
                rec, decision=f"EXECUTION_FAILED:{getattr(exc, 'code', type(exc).__name__)}",
                action_hash=rec.action_hash, policy_hash=active_ph,
                dispositive_rules=["ADAPTER"], applied_constraints=None,
                evidence_hashes=[], approval_hashes=[], stage="failed",
                execution_token_hash=rec.token["token_hash"])
            raise

        # single-use: burn the token nonce so any replay is rejected henceforth
        self._spent_nonces.add(rec.token_nonce)
        result_hash = hashing.domain_digest("EXECUTION_RESULT", jcs.canonicalize(result))
        self._append_audit(
            rec, decision="EXECUTED", action_hash=rec.action_hash, policy_hash=active_ph,
            dispositive_rules=rec.decision["dispositive_rules"],
            applied_constraints=rec.decision.get("applied_constraints"),
            evidence_hashes=[], approval_hashes=[], stage="executed",
            execution_token_hash=rec.token["token_hash"], execution_result_hash=result_hash)
        rec.results.append(result)
        self._transition(rec, S.COMPLETED)
        return {"request_id": request_id, "state": rec.state, "result": result,
                "result_hash": result_hash,
                "credential_id": cred.credential_id}

    # ---------------------------------------------------------------- API: introspection

    def status(self, request_id: str) -> dict:
        rec = self._get(request_id)
        return {
            "request_id": rec.request_id, "state": rec.state,
            "operation": rec.envelope["operation"], "tool": rec.req.tool,
            "verb": rec.req.verb, "action_hash": rec.action_hash,
            "outcome": rec.decision["outcome"] if rec.decision else None,
            "has_token": rec.token is not None,
            "audit_records": len(rec.audit_hashes),
            "results": rec.results,
        }

    def audit_log(self) -> dict:
        return {
            "chain_id": self.chain.chain_id, "head": self.chain.head(),
            "length": len(self.chain.records), "intact": self.chain.verify(),
            "records": [
                {"seq": i, "decision": r["payload"]["decision"],
                 "action_hash": r["payload"]["action_hash"],
                 "record_hash": r["audit_record_hash"]}
                for i, r in enumerate(self.chain.records)],
        }

    def verify_audit(self) -> dict:
        intact = self.chain.verify()
        return {"intact": intact, "length": len(self.chain.records),
                "tamper_index": self.chain.locate_tamper()}

    # ---------------------------------------------------------------- persistence

    def snapshot(self) -> dict:
        """Serialize the reconstructible session state (for the file-backed CLI).

        The signed policy is regenerated deterministically on restore; the broker
        is per-command (issue+use happen in one process) so it is not persisted.
        """
        return {
            "sandbox_root": self.sandbox_root,
            "token_ttl_seconds": self.token_ttl,
            "id_n": self._id_n, "nonce_n": self._nonce_n,
            "spent_nonces": sorted(self._spent_nonces),
            "oracle_ver": self.oracle._ver,
            "chain_records": self.chain.records,
            "records": {rid: {
                "req": dataclasses.asdict(r.req), "envelope": r.envelope,
                "action_hash": r.action_hash, "needed_permission": r.needed_permission,
                "state": r.state, "decision": r.decision, "token": r.token,
                "token_nonce": r.token_nonce, "evidence": r.evidence,
                "approvals": r.approvals, "results": r.results,
                "audit_hashes": r.audit_hashes,
            } for rid, r in self.records.items()},
        }

    @classmethod
    def restore(cls, snap: dict, *, clock=None, broker=None) -> "Gateway":
        gw = cls(sandbox_root=snap["sandbox_root"], clock=clock, broker=broker,
                 token_ttl_seconds=snap.get("token_ttl_seconds", 300))
        gw._id_n = snap["id_n"]
        gw._nonce_n = snap["nonce_n"]
        gw._spent_nonces = set(snap["spent_nonces"])
        gw.oracle._ver = dict(snap["oracle_ver"])
        # rebuild the audit chain by re-appending stored records (recomputes + verifies)
        gw.chain = audit.AuditChain("gateway-session")
        for rec in snap["chain_records"]:
            gw.chain.append(rec)
        for rid, d in snap["records"].items():
            gw.records[rid] = Record(
                request_id=rid, req=ToolRequest(**d["req"]), envelope=d["envelope"],
                action_hash=d["action_hash"], needed_permission=d["needed_permission"],
                state=d["state"], decision=d["decision"], token=d["token"],
                token_nonce=d["token_nonce"], evidence=d["evidence"],
                approvals=d["approvals"], results=d["results"],
                audit_hashes=d["audit_hashes"])
        return gw
