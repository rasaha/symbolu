"""Minimum deterministic gate: state machine + hard-invariant evaluator.

Consumes a validated envelope, a signed policy bundle, evidence, and approvals;
produces one of the six frozen outcomes with a fixed precedence (spec §4/§5/§6).
No broad consequence reasoning, no AI, no BCVF/USE/SCC.

Implementation finding (see IMPLEMENTATION_FINDINGS.md #1): for the irreversible
destructive class DB_DELETE, a missing verified backup resolves to DENY (per
ACTION_GATE_SPECIFICATION.md §10 F3 / §11 A4 / MVP §10 T3), overriding the generic
`MUST_HAVE -> REQUEST_MORE_EVIDENCE` operator mapping in §4 for that hard case.
This affects only the decision outcome, never any hash/approval semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import approval as approval_mod
from . import canon_profile as cp
from . import evidence as evidence_mod
from . import policy as policy_mod
from . import projection, schema
from .errors import GateError

# outcomes (spec §6)
ALLOW = "ALLOW"
ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
SIMULATE_AND_RETRY = "SIMULATE_AND_RETRY"
REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
DENY = "DENY"

# severity: lower = more restrictive (spec §4 precedence). ALLOW_WITH_CONSTRAINTS
# is strictly more restrictive than a bare ALLOW so it wins the tie and carries
# its constraints into the decision.
_SEVERITY = {DENY: 0, REQUEST_MORE_EVIDENCE: 2, SIMULATE_AND_RETRY: 3,
             ESCALATE_TO_HUMAN: 4, ALLOW_WITH_CONSTRAINTS: 5, ALLOW: 6}
_REVERSIBILITY_ORDER = {"REVERSIBLE": 0, "REVERSIBLE_WITH_COST": 1, "IRREVERSIBLE": 2}


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def extract_facts(envelope: dict) -> dict[str, Any]:
    """Deterministic per-operation fact extraction (the 'domain adapter' stub).

    Facts come from the structured `arguments` a real adapter would produce.
    """
    a = envelope.get("arguments", {})
    principal = envelope["credential_scope"]["principal"]
    return {
        "self_grant": principal in set(envelope["target_resource"]) or a.get("grantee") == principal,
        "last_replica": bool(a.get("last_replica", False)),
        "public_sensitive": bool(a.get("public", False)) and bool(a.get("target_sensitive", False)),
        "admin_port_public": a.get("cidr") == "0.0.0.0/0" and bool(a.get("admin_port", False)),
        "widening": bool(a.get("widening", False)),
        "export_unapproved": bool(a.get("export", False)) and not bool(a.get("sink_approved", False)),
        "bulk": bool(a.get("bulk", False)),
        "gate_audit_target": a.get("target") == "gate_audit_path",
        "unbounded": bool(a.get("unbounded", False)),
        "affected_count": str(a.get("affected_count", "0")),
        "trust_root_outside_process": bool(a.get("trust_root_outside", False)),
        "live_dependents": bool(a.get("live_dependents", False)),
        "self_approved": bool(a.get("self_approved", False)),
        "projected_cost": str(a.get("projected_cost", "0")),
        "large_delta": bool(a.get("large_delta", False)),
        "free_text": a.get("content_type") == "free_text",
    }


def _approver_satisfied(envelope, approvals, active_policy_hash, now, used_nonces, algorithm_id):
    """(satisfied, present_but_invalid). Absent -> escalate; invalid -> deny."""
    if not approvals:
        return False, False
    first_err = None
    for ap in approvals:
        try:
            approval_mod.verify_approval(
                ap, envelope, active_policy_hash=active_policy_hash, now=now,
                used_nonces=used_nonces, algorithm_id=algorithm_id)
            return True, False
        except GateError as exc:  # noqa: PERF203
            first_err = first_err or exc
    return False, True  # present but none valid -> DENY


def _attestation_ok(envelope, attn_type, now):
    attn = envelope.get("attestation")
    if not attn:
        return False
    if attn.get("type") != attn_type:
        return False
    exp = attn.get("exp")
    if exp is None:
        return False
    return _parse_ts(now) < _parse_ts(exp)


def _covers(grant, perm):
    return grant == "*" or grant == perm or (grant.endswith(":*") and perm.startswith(grant[:-1]))


def _priv_monotonic(envelope) -> bool:
    """credential_scope.permissions must be covered by delegation_chain grants."""
    grants = [link.get("grant") for link in envelope["delegation_chain"]]
    for perm in envelope["credential_scope"].get("permissions", []):
        if not any(_covers(g, perm) for g in grants if g):
            return False
    return True


def _ticket_self_authored(envelope) -> bool:
    lt = envelope.get("linked_ticket")
    if not lt:
        return False
    author = envelope.get("arguments", {}).get("ticket_author")
    return author is not None and author in (
        envelope["delegator"]["id"], envelope["credential_scope"]["principal"])


def _stale(envelope, now, bound_seconds) -> bool:
    age = (_parse_ts(now) - _parse_ts(envelope["state_freshness"]["as_of"])).total_seconds()
    return age > bound_seconds


def _has_evidence(action_hash, evidence, kind, now, min_fidelity=None):
    for ev in evidence:
        try:
            evidence_mod.verify_binding(ev, action_hash)
        except GateError:
            continue
        if ev["payload"]["kind"] != kind:
            continue
        if not evidence_mod.is_fresh(ev, now):
            continue
        if min_fidelity and not evidence_mod.fidelity_at_least(ev, min_fidelity):
            continue
        return True
    return False


def evaluate(
    envelope: dict, signed_policy: dict, *, evidence: list | None = None,
    approvals: list | None = None, now: str, used_nonces=(),
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> dict:
    """Run the deterministic state machine. Returns a decision dict."""
    evidence = evidence or []
    approvals = approvals or []
    trace = ["RECEIVED"]

    # VALIDATED
    try:
        schema.validate_envelope(envelope)
    except GateError as exc:
        trace.append("VALIDATED")
        return _decision(DENY, [exc.code], None, envelope, None, trace, terminal="DENIED",
                         algorithm_id=algorithm_id, reason=str(exc))
    trace.append("VALIDATED")

    if not policy_mod.verify_policy(signed_policy):
        return _decision(DENY, ["E_POLICY_MISMATCH"], None, envelope, None, trace,
                         terminal="DENIED", algorithm_id=algorithm_id,
                         reason="policy signature/hash invalid")
    active_policy_hash = signed_policy["policy_hash"]

    ah = projection.action_hash(envelope, algorithm_id=algorithm_id)
    facts = extract_facts(envelope)
    rules = [r for r in signed_policy["bundle"]["rules"] if r["operation"] == envelope["operation"]]

    trace.append("INVARIANT_CHECK")
    best = (_SEVERITY[ALLOW], ALLOW, [], None)  # (severity, outcome, rule_ids, constraints)

    def consider(sev, outcome, rule_id, constraints=None):
        nonlocal best
        if sev < best[0]:
            best = (sev, outcome, [rule_id], constraints)
        elif sev == best[0]:
            best[2].append(rule_id)

    # hard pre-checks common to all classes
    if not _priv_monotonic(envelope):
        consider(0, DENY, "PRIV_MONO")
    if _ticket_self_authored(envelope):
        consider(0, DENY, "TICKET_SOD")
    bound = int(signed_policy["bundle"].get("freshness_bound_seconds", "600"))
    if _stale(envelope, now, bound):
        consider(2, REQUEST_MORE_EVIDENCE, "FRESHNESS")

    for rule in rules:
        rid = rule["id"]
        for eff in rule["effects"]:
            op = eff["op"]
            guard = eff.get("when_fact")
            if guard is not None and not facts.get(guard):
                continue
            if op == "DENY":
                consider(0, DENY, rid)
            elif op == "FORBID":
                if facts.get(eff["fact"]):
                    consider(0, DENY, rid)
            elif op == "REQUIRE":
                if not facts.get(eff["fact"]):
                    consider(1 if False else 0, DENY, rid)  # REQUIRE-unmet -> DENY
            elif op == "MUST_HAVE":
                if not _has_evidence(ah, evidence, eff["evidence"], now):
                    if eff.get("hard"):  # finding #1: hard destructive precondition
                        consider(0, DENY, rid)
                    else:
                        consider(2, REQUEST_MORE_EVIDENCE, rid)
            elif op == "REQUIRE_ATTESTATION":
                if not _attestation_ok(envelope, eff["attn_type"], now):
                    consider(2, REQUEST_MORE_EVIDENCE, rid)
            elif op == "REQUIRE_SIMULATION":
                if not _has_evidence(ah, evidence, "simulation", now, min_fidelity=eff["fidelity"]):
                    consider(3, SIMULATE_AND_RETRY, rid)
            elif op == "REQUIRE_APPROVER":
                sat, invalid = _approver_satisfied(
                    envelope, approvals, active_policy_hash, now, used_nonces, algorithm_id)
                if invalid:
                    consider(0, DENY, rid)
                elif not sat:
                    consider(4, ESCALATE_TO_HUMAN, rid)
            elif op in ("MAX_SCOPE", "MAX_COST", "MAX_BLAST_RADIUS"):
                fact_val = int(facts.get(eff["fact"], "0"))
                if fact_val > int(eff["value"]):
                    consider(4, ESCALATE_TO_HUMAN, rid)
            elif op == "MAX_IRREVERSIBILITY":
                if _REVERSIBILITY_ORDER[envelope["reversibility"]] > _REVERSIBILITY_ORDER[eff["class"]]:
                    consider(4, ESCALATE_TO_HUMAN, rid)
            elif op in ("ALLOW", "ALLOW_WITH_CONSTRAINTS"):
                consider(_SEVERITY[op], op, rid, eff.get("constraints"))

    sev, outcome, rule_ids, constraints = best
    if not rules:
        outcome, rule_ids, constraints = ESCALATE_TO_HUMAN, ["NO_RULE"], None

    # trace the checks reached
    for st in ("SIMULATION_CHECK", "CONSEQUENCE_CHECK", "APPROVAL_CHECK", "FINAL_DECISION"):
        trace.append(st)

    terminal = {ALLOW: "COMMITTED", ALLOW_WITH_CONSTRAINTS: "COMMITTED",
                DENY: "DENIED", ESCALATE_TO_HUMAN: "ESCALATED"}.get(outcome, "AUDIT_LOGGED")
    return _decision(outcome, rule_ids, constraints if outcome == ALLOW_WITH_CONSTRAINTS else None,
                     envelope, active_policy_hash, trace, terminal=terminal,
                     algorithm_id=algorithm_id, action_hash=ah)


def _decision(outcome, rule_ids, constraints, envelope, policy_hash, trace, *, terminal,
              algorithm_id, reason="", action_hash=None):
    trace = trace + ["AUDIT_LOGGED", terminal]
    return {
        "outcome": outcome,
        "dispositive_rules": rule_ids,
        "applied_constraints": constraints,
        "action_hash": action_hash,
        "policy_hash": policy_hash,
        "state_trace": trace,
        "terminal": terminal,
        "reason": reason,
        "hash_algorithm_id": algorithm_id,
    }
