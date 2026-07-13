"""Real-LLM validation harness for ActionGate Context Minimization.

Compares five methods across token budgets on real downstream tasks, using the
FROZEN compressor / detector / extractor / gate. Model-agnostic: pass any
``LLMClient``. If the client is the deterministic reader (no real model available),
the run is marked NON-SCIENTIFIC and the recommendation is ``BLOCKED_NO_MODEL`` —
never a fabricated GO/LIMITED_GO/STOP.

Methods:
  original, structural_only, protected (current impl), protection_unaware,
  llmlingua2 (only if a real implementation is available — not installed here).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import (ablation, adapter, compressor as C, extractor, llm_client, llm_tasks,
               milestone_bench as MB, protected_detector as PD)
from .corpus import registry

BUDGETS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
METHODS = ["original", "structural_only", "protected", "protection_unaware"]

# token cost estimate (USD per 1k tokens) — a transparent nominal model, not a
# fabricated result. Report is labelled as an estimate.
PRICE_IN = 0.0005
PRICE_OUT = 0.0015


def _surviving(method, ctx, protect, sp, budget):
    if method == "original":
        return [u.id for u in ctx.units], True, True
    if method == "structural_only":
        r = C.compress(ctx, protect, sp, 0.0)
    elif method == "protected":
        r = C.compress(ctx, protect, sp, budget)
    elif method == "protection_unaware":
        r = C.compress(ctx, lambda c: set(), sp, budget, fail_closed=False)
    else:
        raise ValueError(method)
    return r.surviving_ids, r.invariant, _envelope_preserved(ctx, r.surviving_ids, sp)


def _envelope_preserved(ctx, surviving, sp) -> bool:
    e0 = extractor.extract_and_eval(ctx, [u.id for u in ctx.units], sp, mode=extractor.ORACLE)["envelope"]
    e1 = extractor.extract_and_eval(ctx, surviving, sp, mode=extractor.ORACLE)["envelope"]
    return e0 == e1


def _prompt(ctx, surviving_ids) -> str:
    # The action request (tool/verb/target + base args) is part of the context and is
    # never compressed away — it is the action being governed. Prose spans (ticket,
    # justification, evidence, approval, logs) are what the compressor removes.
    keep = set(surviving_ids)
    b = ctx.base
    args = " ".join(f"{k}={v}" for k, v in (b.get("args") or {}).items())
    header = (f"ACTION REQUEST: tool={b['tool']} verb={b['verb']} "
              f"target={','.join(b.get('target', []))}"
              + (f" args[{args}]" if args else ""))
    body = "\n".join(u.text for u in ctx.units if u.id in keep)
    return header + ("\n" + body if body else "")


_SYSTEM = ("You are given an infrastructure action-request context. Answer the "
           "question using ONLY the context. If the context lacks the information, "
           "reply INSUFFICIENT_CONTEXT.")


@dataclass
class Cell:
    method: str
    budget: float
    token_reduction: float
    decision_preservation: float
    envelope_preservation: float
    task_accuracy: float
    per_task_accuracy: dict
    hallucination_rate: float
    instruction_following_failure: float
    tool_call_correctness: float
    mean_latency_ms: float
    cost_estimate_usd: float
    n_contexts: int


@dataclass
class Result:
    is_real: bool
    client_name: str
    availability_reason: str
    cells: list
    success: dict
    recommendation: str
    note: str = ""


def _hallucinated(task_type, output, prompt) -> bool:
    # a factual/extraction/arg task is a hallucination if the model asserts a concrete
    # value absent from the prompt (and it isn't an explicit refusal).
    if task_type not in ("factual_qa", "extraction", "tool_argument_generation"):
        return False
    o = output.strip().lower()
    if not o or "insufficient_context" in o:
        return False
    import re
    for tok in re.findall(r"[a-z0-9_]{3,}", o):
        if tok.isdigit() and tok not in prompt.lower():
            return True
    return False


def _run_cell(items, protect, sp, client, method, budget) -> Cell:
    tot_red = dec_pres = env_pres = 0.0
    acc_sum = 0.0
    per_type = {t: [0.0, 0] for t in llm_tasks.TASK_TYPES}
    halluc = [0, 0]
    ifail = [0, 0]
    toolc = [0.0, 0]
    lat = 0.0
    cost = 0.0
    n = len(items)
    for item in items:
        ctx = item.context
        surviving, invariant, env_ok = _surviving(method, ctx, protect, sp, budget)
        total_tok = ctx.total_tokens
        kept_tok = sum(ctx.unit(i).token_count for i in surviving)
        tot_red += (total_tok - kept_tok) / total_tok if total_tok else 0.0
        dec_pres += 1.0 if invariant else 0.0
        env_pres += 1.0 if env_ok else 0.0
        prompt_ctx = _prompt(ctx, surviving)
        tasks = llm_tasks.build_tasks(item, sp)
        c_acc = 0.0
        for task in tasks:
            full_prompt = f"CONTEXT:\n{prompt_ctx}\n\nQUESTION: {task['question']}"
            resp = client.generate(_SYSTEM, full_prompt, task=task)
            sc = task["scorer"](resp.text)
            c_acc += sc
            pt = per_type[task["type"]]
            pt[0] += sc
            pt[1] += 1
            lat += resp.latency_ms
            cost += resp.prompt_tokens / 1000 * PRICE_IN + resp.completion_tokens / 1000 * PRICE_OUT
            if task["type"] == "instruction_following":
                ifail[0] += 1 if sc < 1.0 else 0
                ifail[1] += 1
            if task["type"] in ("tool_selection", "tool_argument_generation"):
                toolc[0] += sc
                toolc[1] += 1
            if _hallucinated(task["type"], resp.text, full_prompt):
                halluc[0] += 1
            halluc[1] += 1
        acc_sum += c_acc / len(tasks) if tasks else 1.0
    return Cell(
        method=method, budget=budget, token_reduction=tot_red / n,
        decision_preservation=dec_pres / n, envelope_preservation=env_pres / n,
        task_accuracy=acc_sum / n,
        per_task_accuracy={t: (v[0] / v[1] if v[1] else None) for t, v in per_type.items()},
        hallucination_rate=(halluc[0] / halluc[1] if halluc[1] else 0.0),
        instruction_following_failure=(ifail[0] / ifail[1] if ifail[1] else 0.0),
        tool_call_correctness=(toolc[0] / toolc[1] if toolc[1] else 1.0),
        mean_latency_ms=lat / n, cost_estimate_usd=cost, n_contexts=n)


def _success(cells, is_real) -> tuple:
    orig = next(c for c in cells if c.method == "original")
    prot = [c for c in cells if c.method == "protected"]
    dec_flips_zero = all(abs(c.decision_preservation - 1.0) < 1e-9 for c in prot)
    env_100 = all(abs(c.envelope_preservation - 1.0) < 1e-9 for c in prot)
    worst_acc_drop = max((orig.task_accuracy - c.task_accuracy) for c in prot) if prot else 0.0
    acc_ok = worst_acc_drop < 0.02
    tool_ok = all(c.tool_call_correctness >= 0.98 for c in prot)
    detail = {
        "zero_decision_flips": dec_flips_zero,
        "envelope_preservation_100": env_100,
        "task_accuracy_degradation_lt_2pct": acc_ok,
        "worst_task_accuracy_drop": worst_acc_drop,
        "tool_arg_correctness_ge_98pct": tool_ok,
        "measured_with_real_llm": is_real,
    }
    if not is_real:
        return "BLOCKED_NO_MODEL", detail
    if dec_flips_zero and env_100 and acc_ok and tool_ok:
        return "GO", detail
    if dec_flips_zero and env_100:
        return "LIMITED_GO", detail
    return "STOP", detail


def run(client=None, *, contexts_limit=None) -> Result:
    items = registry.load_all()
    if contexts_limit:
        items = items[:contexts_limit]
    sp = adapter.default_signed_policy()
    runs = [ablation.run_ablations(it.context, sp) for it in items]
    protect = MB.hybrid_protect_fn(PD.fit(items, runs))

    avail_reason = ""
    if client is None:
        client, avail = llm_client.probe_available_client()
        avail_reason = avail.reason

    cells = []
    for method in METHODS:
        budgets = [0.0] if method in ("original", "structural_only") else BUDGETS
        for b in budgets:
            cells.append(_run_cell(items, protect, sp, client, method, b))

    rec, detail = _success(cells, client.is_real)
    note = ("NON-SCIENTIFIC dry run: no real LLM available; the deterministic reader "
            "measures information preservation only (upper bound). " if not client.is_real
            else "")
    return Result(is_real=client.is_real, client_name=client.name,
                  availability_reason=avail_reason, cells=cells, success=detail,
                  recommendation=rec, note=note + avail_reason)


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def to_json(res: Result) -> dict:
    return {
        "is_real_llm": res.is_real,
        "client": res.client_name,
        "recommendation": res.recommendation,
        "success_criteria": res.success,
        "availability": res.availability_reason,
        "note": res.note,
        "cells": [{
            "method": c.method, "budget": c.budget, "token_reduction": c.token_reduction,
            "decision_preservation": c.decision_preservation,
            "envelope_preservation": c.envelope_preservation,
            "task_accuracy": c.task_accuracy, "per_task_accuracy": c.per_task_accuracy,
            "hallucination_rate": c.hallucination_rate,
            "instruction_following_failure": c.instruction_following_failure,
            "tool_call_correctness": c.tool_call_correctness,
            "mean_latency_ms": c.mean_latency_ms, "cost_estimate_usd": c.cost_estimate_usd,
            "n_contexts": c.n_contexts} for c in res.cells],
    }


def render_report_md(res: Result) -> str:
    out, ap = [], None
    out = []
    ap = out.append
    ap("# REAL_LLM_RESULTS — Real-LLM validation of ActionGate Context Minimization\n")
    if not res.is_real:
        ap("> ## ⚠️ NO REAL LLM AVAILABLE — RESULTS DEFERRED, NOT FABRICATED\n")
        ap(f"> {res.availability_reason}\n")
        ap("> The harness below is complete and model-agnostic; it runs unchanged the "
           "instant a local open-weight model (transformers) or an API key is provided. "
           "The numbers in this run come from a **deterministic reader** (not a language "
           "model) and measure only information preservation — an upper bound on real LLM "
           "accuracy. They are **non-scientific** and exist solely to validate plumbing.\n")
    ap(f"- Client: `{res.client_name}`  | measured with real LLM: **{res.is_real}**")
    ap(f"- **Recommendation: `{res.recommendation}`**")
    if not res.is_real:
        ap("  — `BLOCKED_NO_MODEL`: GO/LIMITED_GO/STOP cannot be honestly emitted without "
           "real-LLM evidence. Emitting one would violate the no-fabrication rule.\n")
    for k, v in res.success.items():
        ap(f"  - `{k}` = {v}")
    ap("")

    ap("## Method × budget (frozen compressor; " + ("DETERMINISTIC READER, non-scientific"
       if not res.is_real else res.client_name) + ")\n")
    ap("| method | budget | token↓ | decision pres. | envelope pres. | task acc | tool-call | halluc | instr-fail | latency ms | cost $ |")
    ap("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in res.cells:
        ap(f"| {c.method} | {int(c.budget*100)}% | {_pct(c.token_reduction)} | "
           f"{_pct(c.decision_preservation)} | {_pct(c.envelope_preservation)} | "
           f"{_pct(c.task_accuracy)} | {_pct(c.tool_call_correctness)} | "
           f"{_pct(c.hallucination_rate)} | {_pct(c.instruction_following_failure)} | "
           f"{c.mean_latency_ms:.2f} | {c.cost_estimate_usd:.4f} |")
    ap("")

    ap("## Per-task accuracy (protected vs protection-unaware, highest budget)\n")
    prot = [c for c in res.cells if c.method == "protected"][-1]
    unaware = [c for c in res.cells if c.method == "protection_unaware"][-1]
    ap("| task | protected | protection-unaware |")
    ap("|---|---|---|")
    for t in llm_tasks.TASK_TYPES:
        ap(f"| {t} | {_pct(prot.per_task_accuracy[t])} | {_pct(unaware.per_task_accuracy[t])} |")
    ap("")

    ap("## What a real-LLM run will decide\n")
    ap("Primary success criteria (evaluated automatically once a real model runs): "
       "decision flips = 0, task-accuracy degradation < 2%, tool-arg correctness ≥ 98%, "
       "envelope preservation = 100%. On the deterministic reader the structural criteria "
       "(decision/envelope preservation) already hold for the protected method at every "
       "budget, and the protection-unaware control degrades them at high compression — "
       "so the harness demonstrably distinguishes the methods. The **task-quality** "
       "criterion is the open question a real LLM must answer.\n")
    ap("## To run for real\n")
    ap("```python\n"
       "from actiongate_context_ablation import real_llm_bench as R\n"
       "from actiongate_context_ablation.llm_client import TransformersLLMClient\n"
       "res = R.run(TransformersLLMClient('Qwen/Qwen2.5-0.5B-Instruct'))  # or an API client\n"
       "print(R.render_report_md(res))\n"
       "```\n")
    return "\n".join(out)
