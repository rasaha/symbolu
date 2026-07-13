"""R1 additive remediation projection (advisory metadata only).

Pure, deterministic, side-effect-free projection over an *already-finalized* gate
decision. It explains WHY a decision was reached and WHAT may be required before a fresh
future evaluation. It NEVER changes the outcome, precedence, hashing, approval/evidence/
credential binding, or execution semantics — it only reads the same inputs the gate read.

Design package: ../vnext_remediation/. Reconciliation note (recorded, see
R1_IMPLEMENTATION_FINDINGS.md): the design docs sketched a nested ``remediation`` object
with ``condition_id``/``remediation_class``/``reason_code``; the R1 milestone specifies flat
top-level fields (``response_schema_version``, ``all_unmet_conditions``, ``required_changes``,
``retryability``, ``disclosure``, ``retry_budget``) with ``change_id``/``retry_class``/
``requirement_code``. This module implements the R1 flat schema (the operative spec) with the
design docs' semantics (retry matrix, disclosure gating, DENY-never-retryable, non-
compensatory dominance, hash-invariance).

Correctness guarantee: this module re-uses the gate's OWN predicates (``gate.extract_facts``,
``gate._has_evidence``, ``gate._attestation_ok``, ``gate._approver_satisfied``,
``gate._priv_monotonic``, ``gate._ticket_self_authored``, ``gate._stale``, ``gate._SEVERITY``,
``gate._REVERSIBILITY_ORDER``) rather than re-implementing them, so the unmet-condition set it
reports cannot diverge from what the gate evaluated.
"""

from __future__ import annotations

from typing import Any

from . import canon_profile as cp
from . import gate, policy as policy_mod, projection, schema
from .errors import GateError

RESPONSE_SCHEMA_VERSION = "1.1"

# ---- disclosure modes ----
OFF = "OFF"
MINIMAL = "MINIMAL"
STANDARD = "STANDARD"
TRUSTED_PLANNER = "TRUSTED_PLANNER"
HUMAN_ONLY = "HUMAN_ONLY"
FULL = "FULL"
DISCLOSURE_MODES = (OFF, MINIMAL, STANDARD, TRUSTED_PLANNER, HUMAN_ONLY, FULL)
_PRIVILEGED = (TRUSTED_PLANNER, HUMAN_ONLY, FULL)

# ---- retry classes ----
EVIDENCE_RETRYABLE = "EVIDENCE_RETRYABLE"
SIMULATION_RETRYABLE = "SIMULATION_RETRYABLE"
ACTION_MODIFICATION_RETRYABLE = "ACTION_MODIFICATION_RETRYABLE"
HUMAN_ONLY_CLASS = "HUMAN_ONLY"
TERMINAL = "TERMINAL"
RETRY_CLASSES = (EVIDENCE_RETRYABLE, SIMULATION_RETRYABLE, ACTION_MODIFICATION_RETRYABLE,
                 HUMAN_ONLY_CLASS, TERMINAL)

# security-critical conditions that must ALWAYS be TERMINAL — no policy metadata may make
# them retryable (invariant I3: never turn a DENY-causing hard condition into retryable).
_ALWAYS_TERMINAL = {"FORBID", "REQUIRE", "MUST_HAVE_HARD", "PRIV_MONO", "TICKET_SOD",
                    "APPROVER_INVALID", "NO_RULE_TERMINAL", "PRE_RULE"}


class RemediationDisclosureError(GateError):
    code = "E_REMEDIATION_DISCLOSURE"


class RemediationModeError(GateError):
    code = "E_REMEDIATION_MODE"


# --------------------------------------------------------------------------- #
# unmet-condition collection — mirrors gate.evaluate using the gate's predicates
# --------------------------------------------------------------------------- #
def _mk(rule_id, rule_idx, operator, severity, field_path, slug, *, specifics=None,
        eff_meta=None, terminal_key=None):
    return {"rule_id": rule_id, "rule_idx": rule_idx, "operator": operator,
            "severity": severity, "field_path": field_path, "slug": slug,
            "specifics": specifics or {}, "eff_meta": eff_meta or {},
            "terminal_key": terminal_key}


def _collect_unmet(envelope, signed_policy, evidence, approvals, now, used_nonces,
                   algorithm_id):
    """Return (unmet[], action_hash, pre_rule_terminal_or_None). Pure; reuses gate logic."""
    # pre-rule terminal states (schema / policy) — rules never evaluated here
    try:
        schema.validate_envelope(envelope)
    except GateError as exc:
        return ([_mk(exc.code, -1, "SCHEMA", 0, "envelope", "schema",
                     specifics={"error_code": exc.code}, terminal_key="PRE_RULE")],
                None, exc.code)
    if not policy_mod.verify_policy(signed_policy):
        return ([_mk("E_POLICY_MISMATCH", -1, "POLICY", 0, "policy", "policy",
                     specifics={"error_code": "E_POLICY_MISMATCH"}, terminal_key="PRE_RULE")],
                None, "E_POLICY_MISMATCH")

    ah = projection.action_hash(envelope, algorithm_id=algorithm_id)
    facts = gate.extract_facts(envelope)
    bundle = signed_policy["bundle"]
    active_policy_hash = signed_policy["policy_hash"]
    rules = [(i, r) for i, r in enumerate(bundle["rules"])
             if r["operation"] == envelope["operation"]]
    unmet: list[dict[str, Any]] = []

    # hard pre-checks (same order/logic as gate.evaluate)
    if not gate._priv_monotonic(envelope):
        unmet.append(_mk("PRIV_MONO", -1, "PRIV_MONO", gate._SEVERITY[gate.DENY],
                         "credential_scope.permissions", "priv_mono", terminal_key="PRIV_MONO"))
    if gate._ticket_self_authored(envelope):
        unmet.append(_mk("TICKET_SOD", -1, "TICKET_SOD", gate._SEVERITY[gate.DENY],
                         "linked_ticket", "ticket_sod", terminal_key="TICKET_SOD"))
    bound = int(bundle.get("freshness_bound_seconds", "600"))
    if gate._stale(envelope, now, bound):
        unmet.append(_mk("FRESHNESS", -1, "FRESHNESS", gate._SEVERITY[gate.REQUEST_MORE_EVIDENCE],
                         "state_freshness.as_of", "freshness"))

    for idx, rule in rules:
        rid = rule["id"]
        for eff in rule["effects"]:
            op = eff["op"]
            guard = eff.get("when_fact")
            if guard is not None and not facts.get(guard):
                continue
            meta = eff.get("remediation") or {}
            if op == "DENY":
                unmet.append(_mk(rid, idx, "DENY", 0, f"arguments.{guard}" if guard else "operation",
                                 f"deny:{guard or 'op'}", specifics={"fact": guard},
                                 eff_meta=meta, terminal_key="FORBID"))
            elif op == "FORBID":
                if facts.get(eff["fact"]):
                    unmet.append(_mk(rid, idx, "FORBID", 0, f"arguments.{eff['fact']}",
                                     f"forbid:{eff['fact']}", specifics={"fact": eff["fact"]},
                                     eff_meta=meta, terminal_key="FORBID"))
            elif op == "REQUIRE":
                if not facts.get(eff["fact"]):
                    unmet.append(_mk(rid, idx, "REQUIRE", 0, f"arguments.{eff['fact']}",
                                     f"require:{eff['fact']}", specifics={"fact": eff["fact"]},
                                     eff_meta=meta, terminal_key="REQUIRE"))
            elif op == "MUST_HAVE":
                if not gate._has_evidence(ah, evidence, eff["evidence"], now):
                    if eff.get("hard"):
                        unmet.append(_mk(rid, idx, "MUST_HAVE", 0, f"evidence.{eff['evidence']}",
                                         f"evidence:{eff['evidence']}",
                                         specifics={"kind": eff["evidence"], "hard": True},
                                         eff_meta=meta, terminal_key="MUST_HAVE_HARD"))
                    else:
                        unmet.append(_mk(rid, idx, "MUST_HAVE",
                                         gate._SEVERITY[gate.REQUEST_MORE_EVIDENCE],
                                         f"evidence.{eff['evidence']}", f"evidence:{eff['evidence']}",
                                         specifics={"kind": eff["evidence"], "hard": False},
                                         eff_meta=meta))
            elif op == "REQUIRE_ATTESTATION":
                if not gate._attestation_ok(envelope, eff["attn_type"], now):
                    unmet.append(_mk(rid, idx, "REQUIRE_ATTESTATION",
                                     gate._SEVERITY[gate.REQUEST_MORE_EVIDENCE], "attestation",
                                     f"attestation:{eff['attn_type']}",
                                     specifics={"attn_type": eff["attn_type"]}, eff_meta=meta))
            elif op == "REQUIRE_SIMULATION":
                if not gate._has_evidence(ah, evidence, "simulation", now,
                                          min_fidelity=eff["fidelity"]):
                    unmet.append(_mk(rid, idx, "REQUIRE_SIMULATION",
                                     gate._SEVERITY[gate.SIMULATE_AND_RETRY], "evidence.simulation",
                                     "simulation", specifics={"min_fidelity": eff["fidelity"]},
                                     eff_meta=meta))
            elif op == "REQUIRE_APPROVER":
                sat, invalid = gate._approver_satisfied(
                    envelope, approvals, active_policy_hash, now, used_nonces, algorithm_id)
                if invalid:
                    unmet.append(_mk(rid, idx, "REQUIRE_APPROVER", 0, "approvals", "approver",
                                     specifics={"approver_policy": eff["approver_policy"],
                                                "present_but_invalid": True},
                                     eff_meta=meta, terminal_key="APPROVER_INVALID"))
                elif not sat:
                    unmet.append(_mk(rid, idx, "REQUIRE_APPROVER",
                                     gate._SEVERITY[gate.ESCALATE_TO_HUMAN], "approvals", "approver",
                                     specifics={"approver_policy": eff["approver_policy"]},
                                     eff_meta=meta))
            elif op in ("MAX_SCOPE", "MAX_COST", "MAX_BLAST_RADIUS"):
                fact_val = int(facts.get(eff["fact"], "0"))
                if fact_val > int(eff["value"]):
                    unmet.append(_mk(rid, idx, op, gate._SEVERITY[gate.ESCALATE_TO_HUMAN],
                                     f"arguments.{eff['fact']}", f"{op.lower()}:{eff['fact']}",
                                     specifics={"fact": eff["fact"], "current": str(fact_val),
                                                "limit": str(eff["value"])}, eff_meta=meta))
            elif op == "MAX_IRREVERSIBILITY":
                if gate._REVERSIBILITY_ORDER[envelope["reversibility"]] > \
                        gate._REVERSIBILITY_ORDER[eff["class"]]:
                    unmet.append(_mk(rid, idx, "MAX_IRREVERSIBILITY",
                                     gate._SEVERITY[gate.ESCALATE_TO_HUMAN], "reversibility",
                                     "irreversibility",
                                     specifics={"current": envelope["reversibility"],
                                                "max_class": eff["class"]}, eff_meta=meta))
            # ALLOW / ALLOW_WITH_CONSTRAINTS create no unmet condition

    if not rules:
        unmet.append(_mk("NO_RULE", 999, "NO_RULE", gate._SEVERITY[gate.ESCALATE_TO_HUMAN],
                         "operation", "no_rule", terminal_key="NO_RULE_TERMINAL"))
    return unmet, ah, None


# --------------------------------------------------------------------------- #
# retry classification (grounded matrix, honours optional policy metadata safely)
# --------------------------------------------------------------------------- #
_SEVERITY_DEFAULT_CLASS = {
    0: TERMINAL,
    gate._SEVERITY[gate.REQUEST_MORE_EVIDENCE]: EVIDENCE_RETRYABLE,
    gate._SEVERITY[gate.SIMULATE_AND_RETRY]: SIMULATION_RETRYABLE,
    gate._SEVERITY[gate.ESCALATE_TO_HUMAN]: HUMAN_ONLY_CLASS,
}

_OP_CATEGORY = {
    "MUST_HAVE": "PROVIDE_EVIDENCE", "REQUIRE_ATTESTATION": "PROVIDE_ATTESTATION",
    "REQUIRE_SIMULATION": "RUN_SIMULATION", "REQUIRE_APPROVER": "OBTAIN_APPROVAL",
    "MAX_SCOPE": "REDUCE_SCOPE", "MAX_COST": "REDUCE_COST",
    "MAX_BLAST_RADIUS": "REDUCE_BLAST_RADIUS", "MAX_IRREVERSIBILITY": "REDUCE_IRREVERSIBILITY",
    "FRESHNESS": "REFRESH_STATE", "FORBID": "NONE", "REQUIRE": "NONE", "DENY": "NONE",
    "PRIV_MONO": "NONE", "TICKET_SOD": "NONE", "NO_RULE": "OBTAIN_APPROVAL",
    "SCHEMA": "NONE", "POLICY": "NONE",
}

_OP_CODE = {
    "MUST_HAVE": "R_EVIDENCE_REQUIRED", "REQUIRE_ATTESTATION": "R_ATTESTATION_REQUIRED",
    "REQUIRE_SIMULATION": "R_SIMULATION_REQUIRED", "REQUIRE_APPROVER": "R_APPROVAL_REQUIRED",
    "MAX_SCOPE": "R_SCOPE_EXCEEDED", "MAX_COST": "R_COST_EXCEEDED",
    "MAX_BLAST_RADIUS": "R_BLAST_RADIUS_EXCEEDED",
    "MAX_IRREVERSIBILITY": "R_IRREVERSIBILITY_EXCEEDED", "FRESHNESS": "R_STALE_STATE",
    "FORBID": "R_FORBIDDEN", "REQUIRE": "R_REQUIRE_UNMET", "DENY": "R_FORBIDDEN",
    "PRIV_MONO": "R_PRIV_NON_MONOTONIC", "TICKET_SOD": "R_TICKET_SOD", "NO_RULE": "R_NO_RULE",
    "SCHEMA": "R_SCHEMA_INVALID", "POLICY": "R_POLICY_MISMATCH",
}


# terminal_key refines the requirement code for the security-critical terminal causes
_TERMINAL_CODE = {
    "MUST_HAVE_HARD": "R_HARD_PRECONDITION",
    "APPROVER_INVALID": "R_APPROVAL_INVALID",
    "PRIV_MONO": "R_PRIV_NON_MONOTONIC",
    "TICKET_SOD": "R_TICKET_SOD",
    "NO_RULE_TERMINAL": "R_NO_RULE",
}


def _retry_class(u):
    """Retry class from (operator, hard flag, current outcome, policy metadata). Security-
    critical conditions are forced TERMINAL and cannot be upgraded by policy metadata."""
    tk = u["terminal_key"]
    if tk in _ALWAYS_TERMINAL:
        return TERMINAL
    op = u["operator"]
    base = _SEVERITY_DEFAULT_CLASS.get(u["severity"], TERMINAL)
    # MAX_* default to HUMAN_ONLY; only a policy opt-in makes them action-modification-retryable
    if op in ("MAX_SCOPE", "MAX_COST", "MAX_BLAST_RADIUS", "MAX_IRREVERSIBILITY"):
        opt = (u["eff_meta"].get("retry_class") == ACTION_MODIFICATION_RETRYABLE)
        return ACTION_MODIFICATION_RETRYABLE if opt else HUMAN_ONLY_CLASS
    if op == "REQUIRE_APPROVER":
        return HUMAN_ONLY_CLASS
    if op == "NO_RULE":
        return HUMAN_ONLY_CLASS
    return base


def _requires_new_approval(retry_class, operator):
    return retry_class in (HUMAN_ONLY_CLASS, ACTION_MODIFICATION_RETRYABLE) or \
        operator == "REQUIRE_APPROVER"


def _invalidates_prior_evidence(retry_class):
    # fresh evidence/simulation must be (re)supplied; a modified action re-binds everything
    return retry_class in (EVIDENCE_RETRYABLE, SIMULATION_RETRYABLE,
                           ACTION_MODIFICATION_RETRYABLE)


def _change_id(u):
    return f"chg:{u['rule_id']}:{u['slug']}"


# --------------------------------------------------------------------------- #
# disclosure filtering
# --------------------------------------------------------------------------- #
def _bounds_visible(mode, eff_meta):
    if mode == FULL:
        return True
    if mode in (TRUSTED_PLANNER, HUMAN_ONLY):
        return bool(eff_meta.get("acceptable_bounds_disclosure", False))
    return False   # MINIMAL / STANDARD never reveal exact thresholds


def _full_change(u, policy_version, action_hash, mode):
    rc = _retry_class(u)
    meta = u["eff_meta"]
    category = meta.get("category") or _OP_CATEGORY.get(u["operator"], "NONE")
    code = meta.get("requirement_code") or _TERMINAL_CODE.get(u["terminal_key"]) \
        or _OP_CODE.get(u["operator"], "R_UNKNOWN")
    entry = {
        "change_id": _change_id(u),
        "source_rule_id": u["rule_id"],
        "operator": u["operator"],
        "category": category,
        "field_path": meta.get("field_path") or u["field_path"],
        "requirement_code": code,
        "retry_class": rc,
        "mandatory": True,
        "disclosure_level": meta.get("disclosure_level") or STANDARD,
        "requires_new_approval": _requires_new_approval(rc, u["operator"]),
        "invalidates_prior_evidence": _invalidates_prior_evidence(rc),
        "policy_version": policy_version,
        "action_hash": action_hash,
    }
    # bounds: exact numbers only when policy+mode permit; else a classification
    spec = u["specifics"]
    if {"current", "limit"} <= set(spec):
        if _bounds_visible(mode, meta):
            entry["bounds"] = {"fact": spec.get("fact"), "current": spec["current"],
                               "limit": spec["limit"]}
        else:
            entry["bounds"] = {"classification": "EXCEEDS_LIMIT"}
    elif spec.get("min_fidelity") and mode in (TRUSTED_PLANNER, HUMAN_ONLY, FULL):
        entry["required_fidelity"] = spec["min_fidelity"]
    elif spec.get("kind") and mode in (TRUSTED_PLANNER, HUMAN_ONLY, FULL):
        entry["evidence_kind"] = spec["kind"]
    return entry


def _redact_for_mode(entry, mode):
    """Return the filtered entry per disclosure mode (redaction accounting is central,
    see _collect_redactions). MINIMAL keeps only a broad summary; STANDARD keeps a safe
    structure but never exact thresholds."""
    if mode == MINIMAL:
        keep = ("change_id", "category", "retry_class", "requirement_code", "mandatory")
        return {k: entry[k] for k in keep if k in entry}
    if mode == STANDARD:
        drop = {"required_fidelity", "evidence_kind"}
        out = {k: v for k, v in entry.items() if k not in drop}
        if "bounds" in entry:                       # keep classification, hide numbers
            out["bounds"] = {"classification": "EXCEEDS_LIMIT"}
        return out
    return entry   # TRUSTED_PLANNER / HUMAN_ONLY / FULL: as built


def _unmet_public(u, mode):
    dispositive = u["_dispositive"]
    tier = u["_tier"]
    if mode == MINIMAL:
        return {"dispositive": dispositive, "current_outcome": tier, "evaluated": True}
    return {"rule_id": u["rule_id"], "operator": u["operator"], "dispositive": dispositive,
            "current_outcome": tier, "evaluated": True}


# --------------------------------------------------------------------------- #
# public projection
# --------------------------------------------------------------------------- #
_TIER_BY_SEV = {v: k for k, v in gate._SEVERITY.items()}


def project_remediation(decision, envelope, signed_policy, *, evidence=None, approvals=None,
                        now, disclosure_mode=STANDARD, trusted_context=False, used_nonces=(),
                        algorithm_id=cp.DEFAULT_HASH_ALGORITHM_ID, retry_budget=None):
    """Pure projection → the six additive remediation fields (or {} when OFF).

    Does not mutate ``decision`` or any input. Requires ``now`` explicitly (no wall clock).
    Privileged modes require ``trusted_context=True``.
    """
    if disclosure_mode not in DISCLOSURE_MODES:
        raise RemediationModeError(f"unknown remediation mode {disclosure_mode!r}")
    if disclosure_mode == OFF:
        return {}
    if disclosure_mode in _PRIVILEGED and not trusted_context:
        raise RemediationDisclosureError(
            f"disclosure mode {disclosure_mode} requires a trusted caller context")

    evidence = list(evidence or [])
    approvals = list(approvals or [])
    unmet, action_hash, _pre = _collect_unmet(
        envelope, signed_policy, evidence, approvals, now, tuple(used_nonces), algorithm_id)

    # dispositive severity == the finalized decision's tier (reused from gate predicates)
    min_sev = min((u["severity"] for u in unmet), default=gate._SEVERITY[gate.ALLOW])
    for u in unmet:
        u["_dispositive"] = (u["severity"] == min_sev)
        u["_tier"] = _TIER_BY_SEV[u["severity"]]

    # deterministic ordering: severity, rule order, rule id, field path, change id
    unmet.sort(key=lambda u: (u["severity"], u["rule_idx"], str(u["rule_id"]),
                              u["field_path"], _change_id(u)))

    policy_version = envelope.get("policy_version", "")

    # required_changes = dispositive-tier conditions only (dominance; DENY stays terminal)
    disp = [u for u in unmet if u["_dispositive"]]
    required_changes = []
    seen_ids = set()
    for u in disp:
        entry = _full_change(u, policy_version, action_hash, disclosure_mode)
        filtered = _redact_for_mode(entry, disclosure_mode)
        if filtered["change_id"] in seen_ids:      # no duplicate change entries
            continue
        seen_ids.add(filtered["change_id"])
        required_changes.append(filtered)

    # all_unmet_conditions: FULL-tier callers see every unmet condition; others only the
    # dispositive tier (constraint-fishing containment)
    if disclosure_mode in (TRUSTED_PLANNER, HUMAN_ONLY, FULL):
        all_unmet_src = unmet
    else:
        all_unmet_src = disp
    all_unmet_conditions = [_unmet_public(u, disclosure_mode) for u in all_unmet_src]

    # retryability from the dispositive tier
    if not unmet:
        retryability = {"retryable": False, "retry_class": None,
                        "new_action_hash_required": False, "fresh_evaluation_required": False}
    else:
        disp_class = _dispositive_class(disp)
        retryable = disp_class != TERMINAL
        retryability = {
            "retryable": retryable,
            "retry_class": disp_class,
            "new_action_hash_required": disp_class == ACTION_MODIFICATION_RETRYABLE,
            "fresh_evaluation_required": retryable,
        }

    disclosure = {"mode": disclosure_mode,
                  "redacted_fields": _collect_redactions(disp, disclosure_mode)}

    budget = retry_budget or {}
    retry_budget_out = {"max_attempts": budget.get("max_attempts"),
                        "deadline": budget.get("deadline"),
                        "compute_budget": budget.get("compute_budget")}

    return {
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "all_unmet_conditions": all_unmet_conditions,
        "required_changes": required_changes,
        "retryability": retryability,
        "disclosure": disclosure,
        "retry_budget": retry_budget_out,
    }


def _dispositive_class(disp):
    """The retry class of the dispositive tier. If any dispositive condition is TERMINAL the
    whole action is terminal at that tier (non-compensatory: cannot retry past a DENY)."""
    classes = [_retry_class(u) for u in disp]
    if not classes:
        return TERMINAL
    if TERMINAL in classes:
        return TERMINAL
    # otherwise all dispositive share the tier's class; pick the most restrictive present
    for c in (HUMAN_ONLY_CLASS, ACTION_MODIFICATION_RETRYABLE, SIMULATION_RETRYABLE,
              EVIDENCE_RETRYABLE):
        if c in classes:
            return c
    return classes[0]


def _collect_redactions(disp, mode):
    """Honestly report what a lower disclosure mode withheld, by diffing each dispositive
    change against its FULL reference."""
    if mode not in (MINIMAL, STANDARD):
        return []
    red = set()
    for u in disp:
        full = _full_change(u, "pv", "ah", FULL)          # everything visible
        shown = _redact_for_mode(_full_change(u, "pv", "ah", mode), mode)
        for k in full:
            if k not in shown:
                red.add(k)
        fb = full.get("bounds", {})
        sb = shown.get("bounds", {})
        if "current" in fb and "current" not in sb:
            red.update({"bounds.current", "bounds.limit"})
    return sorted(red)


def attach(decision, remediation_fields):
    """Return a NEW dict = decision + remediation fields (does not mutate ``decision``).
    With an empty remediation (OFF) the decision is returned unchanged (new copy)."""
    out = dict(decision)
    out.update(remediation_fields)
    return out


def decide_with_remediation(gate_module, envelope, signed_policy, *, evidence=None,
                            approvals=None, now, disclosure_mode=OFF, trusted_context=False,
                            used_nonces=(), algorithm_id=cp.DEFAULT_HASH_ALGORITHM_ID,
                            retry_budget=None):
    """Convenience: run the FROZEN gate, then (only if a mode is set) attach remediation.
    The gate decision is finalized first and never influenced by the projection."""
    decision = gate_module.evaluate(envelope, signed_policy, evidence=evidence,
                                    approvals=approvals, now=now, used_nonces=used_nonces,
                                    algorithm_id=algorithm_id)
    if disclosure_mode == OFF:
        return decision
    rem = project_remediation(decision, envelope, signed_policy, evidence=evidence,
                              approvals=approvals, now=now, disclosure_mode=disclosure_mode,
                              trusted_context=trusted_context, used_nonces=used_nonces,
                              algorithm_id=algorithm_id, retry_budget=retry_budget)
    return attach(decision, rem)
