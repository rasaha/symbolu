"""R2 deterministic retry-governance simulator — NO LLM, no planner.

Given a scenario, it repeatedly: evaluates the REAL gate, projects remediation (R1), and
applies a DETERMINISTIC transform for the dispositive required change (attach evidence, run
simulation, narrow scope/cost, choose reversible, refresh state) using the scenario's declared
agent capabilities. It stops at ALLOW*, a terminal/DENY, a human-only escalation, a detected
oscillation, a capability stall, or budget exhaustion.

It changes nothing in ActionGate: it only calls gate.evaluate and remediation.project_remediation
and rebuilds envelopes/evidence for the next attempt. Every action-modifying transform mints a
fresh action_hash (via projection.action_hash), and any prior-action-bound evidence/approval
stops validating — the simulator never reuses authority across action identities and never
mints or uses an execution token.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from action_gate_ref import approval as ap_mod, evidence as ev_mod, gate, projection
from action_gate_ref import remediation as R
from action_gate_ref.errors import GateError

from corpus import NOW, FUTURE, mk_evidence

DEFAULT_MAX_ATTEMPTS = 12
_FIDELITY = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}

# result statuses
ALLOW_SUCCESS = "ALLOW_SUCCESS"
TERMINAL = "TERMINAL"
ESCALATED_HUMAN = "ESCALATED_HUMAN"
OSCILLATION = "OSCILLATION"
EXHAUSTED = "EXHAUSTED"
STUCK = "STUCK"                 # a capability stall (agent cannot perform the required transform)


@dataclass
class SimResult:
    scenario_id: str
    status: str
    retries: int
    trajectory: list = field(default_factory=list)     # per step: outcome, action_hash, retry_class
    action_hashes: list = field(default_factory=list)
    modifications: int = 0                               # action-hash-changing steps
    fresh_hash_on_modification: bool = True              # security invariant
    minted_token: bool = False                           # must stay False
    reused_authority: bool = False                       # must stay False
    saw_deny: bool = False
    ended_after_deny_nonterminal: bool = False           # must stay False (no DENY bypass)


def _fresh(e):
    return ev_mod.is_fresh(e, NOW)


def _bound_fresh_kinds(evidence, ah):
    return frozenset(e["payload"]["kind"] for e in evidence
                     if e["payload"]["bound_to"] == ah and _fresh(e))


def _valid_approver_policies(approvals, env, signed_policy):
    out = set()
    for ap in approvals:
        try:
            ap_mod.verify_approval(ap, env, active_policy_hash=signed_policy["policy_hash"],
                                   now=NOW)
            out.add(ap["payload"]["approver_policy"])
        except GateError:
            continue
    return frozenset(out)


def _kind_from_fieldpath(fp):
    return fp.split(".", 1)[1] if fp.startswith("evidence.") else None


def _apply(retry_class, disp, env, evidence, caps):
    """Deterministic transform. Returns (applied, env, evidence, modified_action)."""
    cat = disp.get("category")
    fp = disp.get("field_path", "")
    if retry_class == R.EVIDENCE_RETRYABLE:
        if cat == "REFRESH_STATE" or disp.get("requirement_code") == "R_STALE_STATE":
            if caps.get("can_refresh_state"):
                env = copy.deepcopy(env)
                env["state_freshness"] = {"as_of": NOW, "source": "live"}
                return True, env, evidence, True     # state is in the action_hash -> fresh hash
            return False, env, evidence, False
        if cat == "PROVIDE_ATTESTATION" or fp == "attestation":
            if caps.get("can_add_attestation"):
                env = copy.deepcopy(env)
                env["attestation"] = {"type": "workload-identity", "evidence": "x",
                                      "exp": "2026-07-12T14:10:00.000Z"}
                return True, env, evidence, False     # attestation excluded from action_hash
            return False, env, evidence, False
        kind = disp.get("evidence_kind") or _kind_from_fieldpath(fp)
        if kind and kind in caps.get("obtainable_evidence", set()):
            vu = NOW if caps.get("evidence_expires") else FUTURE     # NOW == immediately stale
            return True, env, evidence + [mk_evidence(env, kind, valid_until=vu)], False
        return False, env, evidence, False
    if retry_class == R.SIMULATION_RETRYABLE:
        if not caps.get("can_simulate") or caps.get("_resim_used", 0) >= caps.get("resimulate_limit", 99):
            return False, env, evidence, False
        req = disp.get("required_fidelity")
        fid = caps.get("sim_fidelity", "HIGH")
        if req and _FIDELITY.get(fid, 0) < _FIDELITY.get(req, 0):
            return False, env, evidence, False
        caps["_resim_used"] = caps.get("_resim_used", 0) + 1
        vu = NOW if caps.get("evidence_expires") else FUTURE
        return True, env, evidence + [mk_evidence(env, "simulation", fidelity=fid, is_sim=True,
                                                   valid_until=vu)], False
    if retry_class == R.ACTION_MODIFICATION_RETRYABLE:
        if fp == "reversibility" or cat == "REDUCE_IRREVERSIBILITY":
            if caps.get("can_make_reversible"):
                env = copy.deepcopy(env)
                env["reversibility"] = "REVERSIBLE_WITH_COST"
                return True, env, evidence, True
            return False, env, evidence, False
        bounds = disp.get("bounds") or {}
        fact, limit = bounds.get("fact"), bounds.get("limit")
        if fact == "affected_count" and caps.get("can_modify_scope") and limit is not None:
            env = copy.deepcopy(env); env["arguments"] = dict(env["arguments"])
            env["arguments"]["affected_count"] = str(int(limit))
            return True, env, evidence, True
        if fact == "projected_cost" and caps.get("can_reduce_cost") and limit is not None:
            env = copy.deepcopy(env); env["arguments"] = dict(env["arguments"])
            env["arguments"]["projected_cost"] = str(int(limit))
            return True, env, evidence, True
        return False, env, evidence, False
    return False, env, evidence, False


def simulate(scenario, *, max_attempts=DEFAULT_MAX_ATTEMPTS):
    env = copy.deepcopy(scenario.envelope)
    evidence = list(scenario.initial_evidence)
    approvals = list(scenario.initial_approvals)
    caps = dict(scenario.capabilities)
    sp = scenario.signed_policy
    res = SimResult(scenario.scenario_id, EXHAUSTED, 0)
    seen = set()
    prev_ah = None

    for step in range(max_attempts + 1):
        d = gate.evaluate(env, sp, evidence=evidence, approvals=approvals, now=NOW)
        ah = projection.action_hash(env)
        res.action_hashes.append(ah)
        rem = R.project_remediation(d, env, sp, evidence=evidence, approvals=approvals, now=NOW,
                                    disclosure_mode="FULL", trusted_context=True)
        outcome = d["outcome"]
        disp = rem["required_changes"][0] if rem["required_changes"] else None
        rc = disp["retry_class"] if disp else None
        res.trajectory.append({"step": step, "outcome": outcome, "action_hash": ah,
                               "retry_class": rc})
        if outcome == "DENY":
            res.saw_deny = True

        if outcome.startswith("ALLOW"):
            res.status, res.retries = ALLOW_SUCCESS, step
            return res
        key = (ah, _bound_fresh_kinds(evidence, ah),
               _valid_approver_policies(approvals, env, sp), outcome)
        if key in seen:
            res.status, res.retries = OSCILLATION, step
            return res
        seen.add(key)

        if rc == R.TERMINAL or outcome == "DENY":
            res.status, res.retries = TERMINAL, step
            return res
        if rc == R.HUMAN_ONLY_CLASS:
            res.status, res.retries = ESCALATED_HUMAN, step
            return res
        if step == max_attempts:
            res.status, res.retries = EXHAUSTED, step
            return res

        applied, env, evidence, modified = _apply(rc, disp, env, evidence, caps)
        if not applied:
            res.status, res.retries = STUCK, step
            return res
        if modified:
            res.modifications += 1
            new_ah = projection.action_hash(env)
            if new_ah == ah:                      # a modification MUST change the action hash
                res.fresh_hash_on_modification = False
        prev_ah = ah

    res.status, res.retries = EXHAUSTED, max_attempts
    return res
