"""Deterministic, rule-based scoring per task class. No LLM judge.

Each scorer returns {"quality": float in [0,1], "schema_valid": bool,
"components": {...}}. Quality is computed only from the model's text output and
the task's ground truth -- both known offline, so scoring is reproducible.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List


def safe_json(text: str) -> Any:
    """Best-effort parse of a JSON object from model text. None if not parseable."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def _prf(pred: set, gold: set) -> Dict[str, float]:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    r = tp / len(gold) if gold else 1.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def score_extraction(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    fields = task["_oracle"]["fields"]
    if not isinstance(obj, dict):
        return {"quality": 0.0, "schema_valid": False, "components": {"reason": "invalid json"}}
    correct = sum(1 for k, v in fields.items() if str(obj.get(k, "")).strip() == str(v).strip())
    pred_keys = {k for k in fields if k in obj}
    prf = _prf(pred_keys, set(fields))
    acc = correct / len(fields)
    return {"quality": round(acc, 4), "schema_valid": True,
            "components": {"field_accuracy": round(acc, 4), **prf}}


def score_schema_gen(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    fields = task["_oracle"]["fields"]
    if not isinstance(obj, dict) or any(k not in obj for k in fields):
        return {"quality": 0.0, "schema_valid": False,
                "components": {"reason": "schema invalid or missing fields"}}
    correct = sum(1 for k, v in fields.items() if str(obj.get(k, "")).strip() == str(v).strip())
    acc = correct / len(fields)
    return {"quality": round(acc, 4), "schema_valid": True, "components": {"field_accuracy": round(acc, 4)}}


def score_classification(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    if not isinstance(obj, dict) or "label" not in obj:
        return {"quality": 0.0, "schema_valid": False, "components": {"reason": "no label"}}
    ok = 1.0 if str(obj["label"]).strip() == task["_oracle"]["label"] else 0.0
    return {"quality": ok, "schema_valid": True, "components": {"accuracy": ok}}


def score_summarization(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    if not isinstance(obj, dict) or "summary_points" not in obj:
        return {"quality": 0.0, "schema_valid": False, "components": {"reason": "no summary_points"}}
    points = obj["summary_points"] if isinstance(obj["summary_points"], list) else [str(obj["summary_points"])]
    joined = " ".join(str(p).lower() for p in points)
    facts = task["_oracle"]["key_facts"]
    covered = sum(1 for f in facts if _fact_hit(f, joined))
    coverage = covered / len(facts)
    unsupported = any("unsupported" in str(p).lower() for p in points)
    quality = max(0.0, coverage - (0.5 if unsupported else 0.0))
    return {"quality": round(quality, 4), "schema_valid": True,
            "components": {"grounded_coverage": round(coverage, 4),
                           "omission_rate": round(1 - coverage, 4),
                           "unsupported_claim": unsupported}}


def _fact_hit(fact: str, joined: str) -> bool:
    # a fact is "covered" if a distinctive token from it appears
    toks = [t for t in re.findall(r"[a-z0-9:]+", fact.lower()) if len(t) > 3]
    return any(t in joined for t in toks[:3]) if toks else fact.lower() in joined


def score_long_qa(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    if not isinstance(obj, dict) or "answer" not in obj:
        return {"quality": 0.0, "schema_valid": False, "components": {"reason": "no answer"}}
    orc = task["_oracle"]
    ans_ok = 1.0 if orc["answer"].lower() in str(obj.get("answer", "")).lower() else 0.0
    ev_ok = 1.0 if str(obj.get("evidence_id", "")) == orc["evidence_id"] else 0.0
    quality = 0.7 * ans_ok + 0.3 * ev_ok
    return {"quality": round(quality, 4), "schema_valid": True,
            "components": {"answer_correct": ans_ok, "evidence_aligned": ev_ok}}


def score_comparison(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    if not isinstance(obj, dict) or "verdict" not in obj:
        return {"quality": 0.0, "schema_valid": False, "components": {"reason": "no verdict"}}
    ok = 1.0 if str(obj["verdict"]).strip() == task["_oracle"]["verdict"] else 0.0
    return {"quality": ok, "schema_valid": True, "components": {"verdict_correct": ok}}


def score_clause(out_text, task) -> Dict[str, Any]:
    obj = safe_json(out_text)
    if not isinstance(obj, dict) or "clause_ids" not in obj:
        return {"quality": 0.0, "schema_valid": False, "components": {"reason": "no clause_ids"}}
    pred = set(str(x) for x in obj["clause_ids"]) if isinstance(obj["clause_ids"], list) else set()
    gold = set(task["_oracle"]["clause_ids"])
    prf = _prf(pred, gold)
    return {"quality": prf["f1"], "schema_valid": True, "components": prf}


SCORERS = {
    "structured_extraction": score_extraction,
    "schema_constrained_generation": score_schema_gen,
    "classification": score_classification,
    "summarization": score_summarization,
    "long_document_qa": score_long_qa,
    "grounded_comparison": score_comparison,
    "clause_identification": score_clause,
}


def score(task: Dict[str, Any], out_text: str) -> Dict[str, Any]:
    return SCORERS[task["task_class"]](out_text, task)
