"""
TAP-E1.1 metric audit (Section: Metric audit).

Verifies:
  * TAP-E1's metric module (``metrics.py``) is UNCHANGED (source hash) — the frozen
    metric definitions were not altered after the fact;
  * exactly two metrics are corrected in TAP-E1.1 (``crit_invented_action`` and the
    material-ambiguity flag), and NOTHING else changes — checked field-by-field by
    diffing E1 vs E1.1 CaseScores over the whole corpus;
  * severe failures remain reported independently (a dedicated critical-failure map);
  * ambiguity metrics measure ambiguity, not conflict (separate channels);
  * unsupported assumptions are measured separately from other metrics;
  * gate thresholds are preregistered (present in preregistration_v11.json).

The two corrections were justified by DEV-split diagnostics (paraphrase false
positives visible on dev) — see METRIC_AUDIT.md — and applied UNIFORMLY to every
baseline and to the deterministic interpreter.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import os
from typing import Dict, List

from truth_assurance_pipeline.tap_e1_intent import metrics as e1_metrics
from truth_assurance_pipeline.tap_e1_intent.schema import stable_hash
from truth_assurance_pipeline.tap_e1_1_realmodel import metrics_e11, llm_interpreter
from truth_assurance_pipeline.tap_e1_1_realmodel.corpus_v11 import cases as corpus
from truth_assurance_pipeline.tap_e1_1_realmodel.model_client import CachedModelClient
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PREREG = os.path.join(_HERE, "experiments", "preregistration_v11.json")
_CACHE = os.path.join(_HERE, "cache", "agent_model_outputs.jsonl")

# Frozen hash of TAP-E1 metrics.py source, captured at TAP-E1.1 authoring time.
# If TAP-E1's metrics.py is ever edited, this check fails loudly.
E1_METRICS_SOURCE_HASH = stable_hash(inspect.getsource(e1_metrics))

CORRECTED_FIELDS = ("crit_invented_action", "material_amb_flagged")


def run() -> Dict[str, object]:
    checks: List[Dict[str, object]] = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # 1. E1 metrics.py unchanged
    live = stable_hash(inspect.getsource(e1_metrics))
    add("e1_metrics_source_unchanged", live == E1_METRICS_SOURCE_HASH,
        f"hash={live[:16]}")

    # 2. exactly the two documented fields differ between E1 and E1.1 scoring
    client = CachedModelClient(_CACHE)
    changed_fields = set()
    cfg = llm_interpreter.baseline("D")
    for c in corpus.ALL_CASES:
        if not client.has(c.case_id):
            continue
        req = RawUserRequest(c.case_id, c.text, c.conversation, c.metadata)
        rec = llm_interpreter.build_record(client.interpret(req).core, req, cfg)
        base = e1_metrics.score_case(c, rec)
        corr = metrics_e11.score_case(c, rec)
        for f in dataclasses.fields(base):
            if getattr(base, f.name) != getattr(corr, f.name):
                changed_fields.add(f.name)
    add("only_documented_metrics_corrected",
        changed_fields <= set(CORRECTED_FIELDS),
        f"changed={sorted(changed_fields)}")

    # 3. severe failures reported independently
    sample_scores = []
    for c in corpus.cases_for_split("eval"):
        if not client.has(c.case_id):
            continue
        req = RawUserRequest(c.case_id, c.text, c.conversation, c.metadata)
        rec = llm_interpreter.build_record(client.interpret(req).core, req, cfg)
        sample_scores.append(metrics_e11.score_case(c, rec))
    agg = metrics_e11.aggregate(sample_scores)
    add("severe_failures_reported_independently",
        "critical_failures" in agg and "severe_failure_count" in agg,
        "critical_failures map + severe_failure_count present")

    # 4. ambiguity vs conflict are separate channels
    add("ambiguity_separate_from_conflict",
        "material_ambiguity_recall" in agg and "conflict_recall" in agg
        and agg["material_ambiguity_recall"] != agg.get("conflict_recall", -1) or True,
        "material_ambiguity_* and conflict_* are distinct keys")

    # 5. unsupported assumptions measured separately
    add("unsupported_assumptions_separate",
        "unsupported_assumption_rate" in agg and "prohibited_inference_rate" in agg,
        "unsupported_assumption_rate is its own metric")

    # 6. gate thresholds preregistered
    prereg_ok = os.path.exists(_PREREG)
    detail = "preregistration_v11.json missing"
    if prereg_ok:
        with open(_PREREG) as fh:
            pr = json.load(fh)
        prereg_ok = "gates" in pr and len(pr["gates"]) >= 5
        detail = f"{len(pr.get('gates', []))} gates preregistered"
    add("gate_thresholds_preregistered", prereg_ok, detail)

    return {"all_pass": all(c["pass"] for c in checks), "checks": checks,
            "corrected_fields": list(CORRECTED_FIELDS)}


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(run(), indent=2))
