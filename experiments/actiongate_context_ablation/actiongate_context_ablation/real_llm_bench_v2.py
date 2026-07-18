"""V2 absolute-utility benchmark — verdict, eligibility, report.

Separate from V1 (`real_llm_bench.py` is frozen and untouched). Reuses the FROZEN
compression arms and prompt-rendering (`real_llm_bench._surviving` / `._prompt`) so the
compressor, budgets, and arm semantics are byte-identical to V1 — only the TASK SUITE,
SYSTEM prompt, SCORING, and VERDICT differ. All success thresholds below are frozen and
PREREGISTERED (see ABSOLUTE_UTILITY_V2_PREREGISTRATION.md); they are not tuned to any
observed result and no inference has been run to set them.

Verdicts: ABSOLUTE_UTILITY_GO / ABSOLUTE_UTILITY_LIMITED_GO / ABSOLUTE_UTILITY_STOP /
BENCHMARK_NOT_ELIGIBLE, plus BLOCKED_NO_MODEL when no real LLM was used.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import llm_tasks_v2 as T

BENCHMARK_ID = "ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2"
BUDGETS = [0.20, 0.30, 0.40]                      # primary budgets (no frontier this milestone)
METHODS = ["original", "structural_only", "protected", "protection_unaware"]
TASK_TYPES = T.TASK_TYPES

SYSTEM_V2 = ("You are given an infrastructure action-request context. Answer the "
             "question using ONLY the information in the context (and any table or rule "
             "included in the question). If the context lacks the information, reply "
             "INSUFFICIENT_CONTEXT. When asked for JSON, output only the JSON object.")

PRICE_IN = 0.0005
PRICE_OUT = 0.0015

# ---- FROZEN preregistered thresholds --------------------------------------- #
ELIGIBILITY_MIN_ORIGINAL_ACC = 0.60   # the benchmark only certifies absolute utility if
#                                       the uncompressed baseline clears this on answerable tasks
MIN_PROTECTED_ABS_ACC = 0.58          # practical absolute-accuracy floor for protected
MAX_PROTECTED_DEGRADATION = 0.02      # protected vs original: <= 2 percentage points
CRITICAL_TOOL_ARG_MIN = 0.98          # critical tool-argument correctness
CRITICAL_POLICY_MIN = 0.90            # policy / negation / approval critical-task accuracy
STRUCTURAL_UTILITY_MARGIN = 0.02      # protected must not be materially worse than structural_only

ABSOLUTE_UTILITY_GO = "ABSOLUTE_UTILITY_GO"
ABSOLUTE_UTILITY_LIMITED_GO = "ABSOLUTE_UTILITY_LIMITED_GO"
ABSOLUTE_UTILITY_STOP = "ABSOLUTE_UTILITY_STOP"
BENCHMARK_NOT_ELIGIBLE = "BENCHMARK_NOT_ELIGIBLE"
BLOCKED_NO_MODEL = "BLOCKED_NO_MODEL"


@dataclass
class Cell:
    method: str
    budget: float
    token_reduction: float
    decision_preservation: float
    envelope_preservation: float
    protected_recall: float
    task_accuracy: float
    per_task_accuracy: dict
    hallucination_rate: float
    mean_latency_ms: float
    cost_estimate_usd: float
    n_contexts: int


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _family_acc(cells, families):
    vals = []
    for c in cells:
        for fam in families:
            v = c.per_task_accuracy.get(fam)
            if v is not None:
                vals.append(v)
    return _mean(vals)


def _success(cells, is_real) -> tuple:
    orig = next((c for c in cells if c.method == "original"), None)
    struct = next((c for c in cells if c.method == "structural_only"), None)
    prot = [c for c in cells if c.method == "protected"]
    unaware = [c for c in cells if c.method == "protection_unaware"]

    orig_acc = orig.task_accuracy if orig else 0.0
    prot_acc = _mean([c.task_accuracy for c in prot]) or 0.0
    worst_prot_acc = min((c.task_accuracy for c in prot), default=0.0)
    worst_degradation = max((orig_acc - c.task_accuracy for c in prot), default=0.0)

    safety_ok = bool(prot) and all(
        abs(c.decision_preservation - 1.0) < 1e-9
        and abs(c.envelope_preservation - 1.0) < 1e-9
        and abs(c.protected_recall - 1.0) < 1e-9 for c in prot)

    tool_acc = _family_acc(prot, T.CRITICAL_TOOL_ARG_TYPES)
    policy_acc = _family_acc(prot, T.CRITICAL_POLICY_TYPES)
    tool_ok = tool_acc is not None and tool_acc >= CRITICAL_TOOL_ARG_MIN
    policy_ok = policy_acc is not None and policy_acc >= CRITICAL_POLICY_MIN

    abs_ok = worst_prot_acc >= MIN_PROTECTED_ABS_ACC
    degr_ok = worst_degradation <= MAX_PROTECTED_DEGRADATION

    # incremental value vs protection-unaware and vs structural-only
    beats_unaware = bool(unaware) and (
        min(c.decision_preservation for c in prot) >
        min(u.decision_preservation for u in unaware))
    savings_ok = bool(prot) and all(c.token_reduction > 0 for c in prot)
    struct_ok = (struct is None) or (prot_acc >= (struct.task_accuracy - STRUCTURAL_UTILITY_MARGIN))
    incr_ok = beats_unaware and savings_ok and struct_ok

    detail = {
        "benchmark_eligible": orig_acc >= ELIGIBILITY_MIN_ORIGINAL_ACC,
        "original_absolute_accuracy": orig_acc,
        "protected_absolute_accuracy_mean": prot_acc,
        "protected_absolute_accuracy_worst": worst_prot_acc,
        "worst_protected_degradation": worst_degradation,
        "safety_zero_flips_env_recall": safety_ok,
        "critical_tool_arg_accuracy": tool_acc,
        "critical_policy_accuracy": policy_acc,
        "absolute_floor_met": abs_ok,
        "degradation_within_2pct": degr_ok,
        "critical_tool_arg_ge_98pct": tool_ok,
        "critical_policy_ge_threshold": policy_ok,
        "beats_protection_unaware": beats_unaware,
        "positive_token_savings": savings_ok,
        "not_worse_than_structural": struct_ok,
        "measured_with_real_llm": is_real,
    }

    if not is_real:
        return BLOCKED_NO_MODEL, detail
    if orig_acc < ELIGIBILITY_MIN_ORIGINAL_ACC:
        return BENCHMARK_NOT_ELIGIBLE, detail
    if not safety_ok:
        return ABSOLUTE_UTILITY_STOP, detail
    core = safety_ok and abs_ok and degr_ok
    if core and tool_ok and policy_ok and incr_ok:
        return ABSOLUTE_UTILITY_GO, detail
    if core:
        return ABSOLUTE_UTILITY_LIMITED_GO, detail
    return ABSOLUTE_UTILITY_STOP, detail


def to_json(recommendation, detail, cells, is_real) -> dict:
    return {
        "benchmark_id": BENCHMARK_ID,
        "is_real_llm": is_real,
        "recommendation": recommendation,
        "success_criteria": detail,
        "cells": [{
            "method": c.method, "budget": c.budget, "token_reduction": c.token_reduction,
            "decision_preservation": c.decision_preservation,
            "envelope_preservation": c.envelope_preservation,
            "protected_recall": c.protected_recall,
            "task_accuracy": c.task_accuracy, "per_task_accuracy": c.per_task_accuracy,
            "hallucination_rate": c.hallucination_rate,
            "mean_latency_ms": c.mean_latency_ms, "cost_estimate_usd": c.cost_estimate_usd,
            "n_contexts": c.n_contexts} for c in cells],
    }


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def render_report_md(recommendation, detail, cells, is_real) -> str:
    out = []
    ap = out.append
    ap("# ABSOLUTE_UTILITY_V2_RESULTS — ActionGate Context Minimization (V2 benchmark)\n")
    ap(f"- Benchmark: `{BENCHMARK_ID}`  | measured with real LLM: **{is_real}**")
    ap(f"- **Recommendation: `{recommendation}`**\n")
    if not is_real:
        ap("> `BLOCKED_NO_MODEL` — no real LLM was used; no graded verdict is emitted "
           "(no fabrication).\n")
    ap("## Preregistered success criteria (frozen before inference)\n")
    for k, v in detail.items():
        ap(f"- {k}: {v}")
    ap("\n## Cells (method × budget)\n")
    ap("| method | budget | token↓ | dec.pres | env.pres | prot.recall | task acc |")
    ap("|---|---|---|---|---|---|---|")
    for c in cells:
        ap(f"| {c.method} | {int(c.budget*100)}% | {_pct(c.token_reduction)} | "
           f"{_pct(c.decision_preservation)} | {_pct(c.envelope_preservation)} | "
           f"{_pct(c.protected_recall)} | {_pct(c.task_accuracy)} |")
    ap("")
    return "\n".join(out)
