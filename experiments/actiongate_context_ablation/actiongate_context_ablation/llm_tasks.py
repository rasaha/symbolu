"""Downstream-task suite for the real-LLM validation harness.

Every task's ground truth is derived from the FROZEN ActionGate envelope/decision on
the ORIGINAL context, so grading is model-agnostic and deterministic. A task is a
dict: {type, question, answer_key, answer_span, scorer}. ``answer_span`` is the
text whose survival makes the answer recoverable (used by the deterministic reader
and by hallucination checks).

Task types (per milestone): instruction_following, factual_qa, reasoning,
summarization, extraction, tool_selection, tool_argument_generation,
actiongate_envelope_extraction. (ActionGate decision invariance / envelope
preservation are computed structurally by the harness, not via the LLM.)
"""

from __future__ import annotations

import json

from . import adapter, extractor


def _orig_eval(ctx, sp):
    return extractor.extract_and_eval(ctx, [u.id for u in ctx.units], sp, mode=extractor.ORACLE)


def _first_span_with(ctx, key_pred):
    for u in ctx.units:
        if key_pred(u):
            return u
    return None


def _grade_exact(answer_key):
    key = str(answer_key).strip().lower()
    return lambda out: 1.0 if key and key in out.strip().lower() else 0.0


def _grade_contains_all(keys):
    ks = [str(k).strip().lower() for k in keys if str(k).strip()]
    return lambda out: (sum(1 for k in ks if k in out.lower()) / len(ks)) if ks else 1.0


def build_tasks(item, sp) -> list:
    ctx = item.context
    res = _orig_eval(ctx, sp)
    env, dec = res["envelope"], res["decision"]
    tool = env["tool"]["server_id"]
    verb = env["tool"]["tool_name"]
    outcome = dec["outcome"]
    args = env.get("arguments", {})
    tasks = []

    # tool_selection
    tasks.append({
        "type": "tool_selection",
        "question": f"Which tool and verb execute this action? Answer as tool.verb.",
        "answer_key": f"{tool}.{verb}", "answer_span": f"{tool}",
        "scorer": _grade_exact(f"{tool}.{verb}")})

    # tool_argument_generation (decision-relevant arg keys)
    if args:
        arg_json = json.dumps(args, sort_keys=True)
        span = _first_span_with(ctx, lambda u: any(str(v).lower() in (u.text or "").lower()
                                                   for v in args.values()))
        tasks.append({
            "type": "tool_argument_generation",
            "question": "Produce the JSON arguments for this action.",
            "answer_key": arg_json,
            "answer_span": (span.text if span else arg_json),
            "scorer": _grade_contains_all([str(v) for v in args.values()])})

    # factual_qa — affected count / amount if present
    if "affected_count" in args:
        span = _first_span_with(ctx, lambda u: str(args["affected_count"]) in (u.text or ""))
        tasks.append({
            "type": "factual_qa",
            "question": "How many records/resources does this action affect?",
            "answer_key": str(args["affected_count"]),
            "answer_span": (span.text if span else str(args["affected_count"])),
            "scorer": _grade_exact(str(args["affected_count"]))})

    # reasoning — is this action admissible?
    span = _first_span_with(ctx, lambda u: u.source_type in ("approval_record", "evidence_record"))
    tasks.append({
        "type": "reasoning",
        "question": ("Based on the context, what is the governance disposition of this "
                     "action? Answer with one of ALLOW/ALLOW_WITH_CONSTRAINTS/"
                     "SIMULATE_AND_RETRY/REQUEST_MORE_EVIDENCE/ESCALATE_TO_HUMAN/DENY."),
        "answer_key": outcome,
        "answer_span": (span.text if span else outcome),
        "scorer": _grade_exact(outcome)})

    # instruction_following — strict format
    tasks.append({
        "type": "instruction_following",
        "question": ("Reply with EXACTLY the operation name in upper snake case and "
                     "nothing else."),
        "answer_key": env["operation"], "answer_span": f"{verb}",
        "scorer": _grade_exact(env["operation"])})

    # extraction — evidence kinds present
    ev_spans = [u for u in ctx.units if u.source_type == "evidence_record"]
    if ev_spans:
        kinds = []
        for u in ev_spans:
            for e in u.contrib.get("evidence", []):
                kinds.append(e["kind"])
        tasks.append({
            "type": "extraction",
            "question": "List the kinds of evidence/attestation provided for this action.",
            "answer_key": ", ".join(sorted(set(kinds))),
            "answer_span": (ev_spans[0].text),
            "scorer": _grade_contains_all(sorted(set(kinds)))})

    # summarization — must retain the decision-relevant facts
    approvers = "approval" if any(u.source_type == "approval_record" for u in ctx.units) else ""
    key_facts = [tool, verb] + ([str(args["affected_count"])] if "affected_count" in args else [])
    tasks.append({
        "type": "summarization",
        "question": "Summarize this action request in one sentence, preserving the key facts.",
        "answer_key": " ".join(key_facts),
        "answer_span": (ctx.units[0].text if ctx.units else ""),
        "scorer": _grade_contains_all(key_facts)})

    # actiongate_envelope_extraction — reconstruct operation+tool+verb
    tasks.append({
        "type": "actiongate_envelope_extraction",
        "question": ("Extract the ActionGate envelope core as JSON with keys "
                     "operation, tool, verb."),
        "answer_key": json.dumps({"operation": env["operation"], "tool": tool, "verb": verb},
                                 sort_keys=True),
        "answer_span": f"{tool}",
        "scorer": _grade_contains_all([env["operation"], tool, verb])})

    return tasks


TASK_TYPES = ["tool_selection", "tool_argument_generation", "factual_qa", "reasoning",
              "instruction_following", "extraction", "summarization",
              "actiongate_envelope_extraction"]
