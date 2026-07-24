"""Full counterfactual execution: run every eligible model on every task.

For each task we run every hard/technically-eligible model, capture the raw
response, validate schema, score quality, and record latency + modeled cost +
retries. Raw and normalized stores are written separately.

With real adapters this makes real API calls (guarded by CostGuard). With the
stub adapter it runs offline and records a MODELED cost (registry price x tokens)
so economics are visible; those numbers are self-test artifacts, not evidence.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from model_selection_pilot import costguard as cg
from model_selection_pilot import policy as pol
from model_selection_pilot import scoring as scoring
from model_selection_pilot.provider import ModelAdapter, StubAdapter


def technically_eligible(registry: Dict[str, Any], task: Dict[str, Any]) -> List[str]:
    """Hard + technical eligibility (steps 1-2 of the policy), used to bound the
    counterfactual: we never run a model that is provider/technically ineligible."""
    view = pol.routing_view(task)
    ent = registry["enterprise_policy"]
    out = []
    for mid, model in registry["models"].items():
        ok, *_ = pol.hard_and_technical_filter(mid, model, view, ent)
        if ok:
            out.append(mid)
    return out


def build_prompt(task: Dict[str, Any]) -> str:
    schema = task.get("required_schema", {})
    fields = schema.get("fields", [])
    instr = {
        "structured_extraction": "Extract the fields as JSON.",
        "schema_constrained_generation": "Return ONLY valid JSON with exactly these fields.",
        "classification": f"Classify into one of {task.get('label_set')}. Return JSON {{'label': ...}}.",
        "summarization": "Summarize as JSON {'summary_points': [...]}, grounded only in the text.",
        "long_document_qa": f"Answer the question from the document. Question: {task.get('question')}. "
                            "Return JSON {'answer':..., 'evidence_id':...}.",
        "grounded_comparison": "Return JSON {'verdict': ...}.",
        "clause_identification": "Return JSON {'clause_ids': [...]} for the requested clause type.",
    }[task["task_class"]]
    return f"{instr}\nRequired fields: {fields}\n---\n{task['input_text']}"


def run_counterfactual(registry: Dict[str, Any], adapters: Dict[str, ModelAdapter],
                       tasks: List[Dict[str, Any]], guard: cg.CostGuard,
                       max_out_tokens: int = 400) -> Dict[str, Any]:
    """Returns {task_id: {model_id: result}} and writes raw/normalized stores."""
    normalized: Dict[str, Dict[str, Any]] = {}
    raw: Dict[str, Dict[str, Any]] = {}
    for task in tasks:
        tid = task["task_id"]
        normalized[tid] = {}
        raw[tid] = {}
        for mid in technically_eligible(registry, task):
            adapter = adapters[mid]
            model = registry["models"][mid]
            if isinstance(adapter, StubAdapter):
                res = adapter.generate_for_task(task)
            else:  # real adapter: guard real spend
                est = cg.estimate_task_cost(model, task, max_out_tokens)
                guard.check(est)
                res = adapter.generate(build_prompt(task), task.get("required_schema"), max_out_tokens)
            actual_cost = cg.model_call_cost(model, res.prompt_tokens, res.completion_tokens)
            if adapter.is_real:
                guard.charge(actual_cost)
            sc = scoring.score(task, res.text)
            normalized[tid][mid] = {"quality": sc["quality"], "schema_valid": sc["schema_valid"],
                                    "components": sc["components"], "cost_usd": round(actual_cost, 8),
                                    "latency_ms": res.latency_ms, "retries": res.retries,
                                    "error": res.error, "is_real": adapter.is_real}
            raw[tid][mid] = {"output_text": res.text[:2000], "prompt_tokens": res.prompt_tokens,
                             "completion_tokens": res.completion_tokens, "error": res.error}
    return {"normalized": normalized, "raw": raw}
