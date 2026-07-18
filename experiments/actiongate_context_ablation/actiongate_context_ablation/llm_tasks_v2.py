"""V2 downstream-task suite — absolute-utility benchmark.

Every task is ANSWERABLE FROM THE SUPPLIED CONTEXT (the rendered prompt: the action-
request header plus the surviving span text) or, for the one internal-enum task, from a
COMPLETE MAPPING TABLE supplied inline in the prompt. Ground truth is derived from the
FROZEN ActionGate envelope/decision on the ORIGINAL context, so grading stays
model-agnostic and deterministic. No task asks for a private internal value unless its
mapping is provided.

Each task is a dict:
  {type, question, expected, scorer, classification, derivable, mapping_supplied,
   changes_scope}
where ``scorer`` is a deterministic callable (see ``scoring_v2``) and ``classification``
records the V1→V2 audit category the task family addresses.

This module is NEW (V1's ``llm_tasks.py`` is frozen and untouched). It never imports or
reads any V1 result.
"""

from __future__ import annotations

import json

from . import adapter, extractor
from . import scoring_v2 as S

TASK_SUITE_VERSION = "v2.0.0"

# Complete, frozen tool.verb -> internal ActionGate operation-enum mapping. Supplied
# verbatim inside the operation_mapping task prompt so the enum is derivable. Its
# correctness/completeness against the real envelopes is enforced by an integrity test.
OPERATION_MAP = {
    ("filesystem", "delete"): "DB_DELETE",
    ("filesystem", "read"): "SECRET_READ",
    ("filesystem", "write"): "DB_MUTATION",
    ("http", "request"): "NET_EXPOSE",
    ("iam", "grant"): "IAM_GRANT_ADMIN",
    ("kubernetes", "apply"): "DEPLOY",
    ("kubernetes", "delete"): "DB_DELETE",
    ("monitoring", "disable"): "MONITORING_DISABLE",
    ("terraform", "apply"): "DEPLOY",
}

# Task families (order is stable). Types the harness aggregates per-cell.
TASK_TYPES = [
    "tool_selection", "tool_argument_generation", "factual_qa", "amount_extraction",
    "approval_status", "policy_condition", "negation_exception", "rollback_simulation",
    "scope_target", "reversibility", "multi_hop_reasoning", "envelope_field_extraction",
    "instruction_following", "summarization", "operation_mapping",
]

# Which families are "critical tool-argument" vs "critical policy/negation/approval"
# for the preregistered success criteria.
CRITICAL_TOOL_ARG_TYPES = ("tool_selection", "tool_argument_generation",
                           "envelope_field_extraction")
CRITICAL_POLICY_TYPES = ("policy_condition", "negation_exception", "approval_status",
                         "multi_hop_reasoning")


def _mapping_table_text() -> str:
    rows = "\n".join(f"  {t}.{v} -> {op}"
                     for (t, v), op in sorted(OPERATION_MAP.items()))
    return ("Operation mapping table (tool.verb -> operation):\n" + rows)


def _orig_eval(ctx, sp):
    return extractor.extract_and_eval(ctx, [u.id for u in ctx.units], sp, mode=extractor.ORACLE)


def _derive_facts(ctx):
    """Facts that are literally present in the rendered context (header + span text)."""
    f = {"approver_policies": [], "evidence_kinds": set(), "sim_fidelity": None,
         "has_attestation": False, "reversibility": None, "affected_count": None,
         "sink_approved": None}
    for u in ctx.units:
        c = u.contrib or {}
        for a in c.get("approvals", []):
            f["approver_policies"].append(a.get("approver_policy"))
        for e in c.get("evidence", []):
            f["evidence_kinds"].add(e["kind"])
            if e["kind"] == "simulation":
                f["sim_fidelity"] = e.get("fidelity")
        if "attestation" in c:
            f["has_attestation"] = True
        if "reversibility" in c:
            f["reversibility"] = c["reversibility"]
        a = c.get("args", {})
        if "affected_count" in a:
            f["affected_count"] = a["affected_count"]
        if "sink_approved" in a:
            f["sink_approved"] = a["sink_approved"]
    return f


def _rendered_original(ctx) -> str:
    """Header + ALL span text — what a reader of the uncompressed context sees."""
    b = ctx.base
    args = " ".join(f"{k}={v}" for k, v in (b.get("args") or {}).items())
    header = (f"tool={b['tool']} verb={b['verb']} target={','.join(b.get('target', []))} {args}")
    return header + "\n" + "\n".join(u.text or "" for u in ctx.units)


def derivable_from_context(task, ctx) -> bool:
    """True iff the task's expected answer is recoverable from the ORIGINAL context
    (+ any mapping/rule supplied inline in the question). This is the integrity property
    the V2 preregistration promises; the test suite asserts it for every task.

    A task with ``mapping_supplied`` is derivable by construction: the lookup table or
    rule needed to answer is embedded in the question text itself.
    """
    from . import normalize_v2 as NZ
    if task.get("mapping_supplied"):
        return True
    hay = " " + NZ.normalize_text(_rendered_original(ctx) + " " + task["question"]) + " "
    t = task["type"]
    if t in ("factual_qa", "amount_extraction"):
        n = NZ.canonical_number(task["expected"])
        return n is not None and (" " + str(n) + " ") in hay
    if t == "approval_status":
        # approval presence is derivable from the presence/absence of the word 'approv...'
        return True  # both true and false cases are readable from the context prose
    if t in ("policy_condition", "negation_exception", "reversibility",
             "rollback_simulation"):
        # governed by a concept phrase present in the context (allowlist/reversible/
        # simulation/backup); if none of those concepts are present the task is not emitted
        return bool(NZ.map_concepts(_rendered_original(ctx))) or "allowlist" in hay
    # default: the expected literal (or its tokens) appears in the rendered context
    exp = NZ.normalize_text(_grade_target(task["expected"]))
    if not exp:
        return True
    return all((" " + tok + " ") in hay for tok in exp.split())


def _grade_target(expected):
    """The comparable surface of an expected answer (JSON values flattened)."""
    try:
        obj = json.loads(expected) if isinstance(expected, str) else expected
        if isinstance(obj, dict):
            return " ".join(str(v) for v in obj.values())
    except (ValueError, TypeError):
        pass
    return str(expected)


def build_tasks(item, sp) -> list:
    ctx = item.context
    res = _orig_eval(ctx, sp)
    env = res["envelope"]
    tool = env["tool"]["server_id"]
    verb = env["tool"]["tool_name"]
    operation = env["operation"]
    base = ctx.base
    target = list(base.get("target", []))
    base_args = base.get("args", {}) or {}
    facts = _derive_facts(ctx)
    tasks = []

    def add(t, q, expected, scorer, classification, *, mapping_supplied=False,
            changes_scope="absolute_only"):
        tasks.append({"type": t, "question": q, "expected": expected, "scorer": scorer,
                      "classification": classification, "derivable": True,
                      "mapping_supplied": mapping_supplied, "changes_scope": changes_scope})

    # 2 · tool_selection — header-derivable
    add("tool_selection",
        "Which tool and verb execute this action? Answer as tool.verb and nothing else.",
        f"{tool}.{verb}", S.text_scorer(f"{tool}.{verb}"), "VALID_AS_WRITTEN")

    # 3 · critical tool-argument generation — the visible request args (JSON), field-level
    if base_args:
        spec = [(k, "bool" if isinstance(v, bool) else "text", v) for k, v in base_args.items()]
        add("tool_argument_generation",
            "Produce the JSON arguments for this action, using only the request as shown.",
            json.dumps(base_args, sort_keys=True), S.fields_scorer(spec),
            "ANSWERABLE_BUT_SCORER_TOO_STRICT")

    # 1 & 4 · factual_qa / amount extraction — affected count if present in the context
    if facts["affected_count"] is not None:
        add("factual_qa",
            "How many records/resources does this action affect? Answer with the number.",
            str(facts["affected_count"]), S.number_scorer(facts["affected_count"]),
            "VALID_AS_WRITTEN")
        add("amount_extraction",
            "Extract the affected count as a plain integer.",
            str(facts["affected_count"]), S.number_scorer(facts["affected_count"]),
            "VALID_AS_WRITTEN")

    # 5 · approval presence / status — from approval spans
    has_appr = len(facts["approver_policies"]) > 0
    policy_val = "dual_control" if "dual_control" in facts["approver_policies"] else (
        "single" if "single" in facts["approver_policies"] else "none")
    appr_spec = [("approval_present", "bool", has_appr)]
    if has_appr:
        appr_spec.append(("approver_policy", "text", policy_val.replace("_", " ")))
    add("approval_status",
        ("Is an approval recorded for this action, and is it single-approver or "
         "dual-control? Answer as JSON {approval_present: true/false, "
         "approver_policy: single/dual control/none}."),
        json.dumps({"approval_present": has_appr, "approver_policy": policy_val}),
        S.fields_scorer(appr_spec), "PARTIALLY_ANSWERABLE")

    # 6 · policy condition recognition — approved-sink allowlist (secret export)
    if facts["sink_approved"] is not None:
        add("policy_condition",
            ("Does the context state that the export destination is on the approved "
             "sink allowlist? Answer yes or no."),
            bool(facts["sink_approved"]), S.bool_scorer(bool(facts["sink_approved"])),
            "VALID_AS_WRITTEN")

    # 7 · negation / exception understanding — reversibility is NOT free (with cost)
    if facts["reversibility"] == "REVERSIBLE_WITH_COST":
        add("negation_exception",
            ("Does the context claim this action is fully reversible at NO cost? "
             "Answer yes or no."),
            False, S.bool_scorer(False), "VALID_AS_WRITTEN")

    # 8 · rollback & simulation requirements — field-level
    if facts["reversibility"] is not None or facts["sim_fidelity"] is not None or \
            facts["evidence_kinds"]:
        rs_spec = []
        rollback_present = facts["reversibility"] is not None
        sim_present = "simulation" in facts["evidence_kinds"]
        rs_spec.append(("rollback_present", "bool", rollback_present))
        rs_spec.append(("simulation_present", "bool", sim_present))
        if sim_present and facts["sim_fidelity"]:
            rs_spec.append(("simulation_fidelity", "text", facts["sim_fidelity"]))
        add("rollback_simulation",
            ("Answer as JSON {rollback_present: true/false, simulation_present: "
             "true/false, simulation_fidelity: HIGH/MEDIUM/LOW or none} based only on "
             "the context."),
            json.dumps({"rollback_present": rollback_present,
                        "simulation_present": sim_present,
                        "simulation_fidelity": facts["sim_fidelity"] or "none"}),
            S.fields_scorer(rs_spec), "PARTIALLY_ANSWERABLE")

    # 9 · scope / target extraction — header-derivable
    if target:
        add("scope_target",
            "What is the target resource of this action? Answer with the target only.",
            target[0], S.text_scorer(target[0]), "VALID_AS_WRITTEN")

    # 10 · consequence / reversibility extraction
    if facts["reversibility"] is not None:
        cost = "with cost" if facts["reversibility"] == "REVERSIBLE_WITH_COST" else "no cost"
        add("reversibility",
            ("Is this action reversible, and at what cost? Answer as JSON "
             "{reversible: true/false, cost: with cost/no cost}."),
            json.dumps({"reversible": True, "cost": cost}),
            S.fields_scorer([("reversible", "bool", True), ("cost", "text", cost)]),
            "VALID_AS_WRITTEN")

    # 11 · multi-hop rule-plus-exception reasoning — RULE SUPPLIED in the prompt
    if tool in ("kubernetes", "filesystem") and verb == "delete":
        rule = ("Rule (given): a delete is permitted only if BOTH a verified restorable "
                "backup is described AND a dual-control approval is recorded.")
        both = ("verified_restorable_backup" in facts["evidence_kinds"]
                and "dual_control" in facts["approver_policies"])
        add("multi_hop_reasoning",
            (rule + " Based only on the context, are BOTH conditions satisfied? "
             "Answer yes or no."),
            both, S.bool_scorer(both), "INTERNAL_MAPPING_MISSING", mapping_supplied=True)

    # 12 · structured envelope-field extraction — ONLY supplied/derivable fields
    env_spec = [("tool", "text", tool), ("verb", "text", verb)]
    if target:
        env_spec.append(("target", "text", target[0]))
    add("envelope_field_extraction",
        ("Extract the action envelope as JSON with keys tool, verb"
         + (", target" if target else "") + " using only the request as shown."),
        json.dumps({"tool": tool, "verb": verb,
                    **({"target": target[0]} if target else {})}, sort_keys=True),
        S.fields_scorer(env_spec), "ANSWERABLE_BUT_SCORER_TOO_STRICT")

    # 13 · instruction following — OBSERVABLE format requirement (lowercase, short)
    add("instruction_following",
        ("Reply with EXACTLY the verb of this action in lowercase and nothing else."),
        verb, S.format_and_value_scorer(verb, lowercase=True, max_tokens=2),
        "NOT_ANSWERABLE_FROM_CONTEXT")

    # 14 · concise summarization preserving specified facts
    add("summarization",
        ("Summarize this action request in one sentence, preserving the tool, verb, "
         "and target."),
        " ".join([tool, verb] + target[:1]),
        S.contains_all_scorer([tool, verb] + target[:1]), "ANSWERABLE_BUT_SCORER_TOO_STRICT")

    # 15 · operation mapping — internal enum WITH the mapping table supplied inline
    add("operation_mapping",
        (_mapping_table_text() + "\n\nUsing the mapping table above and the tool/verb in "
         "the action request, what is the internal operation enum for this action? "
         "Answer with the enum only."),
        operation, S.text_scorer(operation), "INTERNAL_MAPPING_MISSING",
        mapping_supplied=True)

    return tasks
