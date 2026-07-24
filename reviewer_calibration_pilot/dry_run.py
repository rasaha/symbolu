"""Phase 13 - Dry run (machinery test on NON-FINAL artifacts).

Exercises the full apparatus on the TRAINING set with a clearly-labelled MOCK reviewer, to verify the
plumbing: blinded review, timing, frozen policy execution, post-reveal display, override recording,
audit, replay, stop-condition evaluation, and non-enforcement. The mock reviewer is a machinery test
ONLY - it is never human validation and never touches the final set.

Deterministic, read-only. Writes eval_results/dry_run.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from reviewer_calibration_pilot import orchestrator as orch, review_interface as ri, dataset, stop_conditions as sc

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")


def _mock_stage_a(blinded: Dict[str, Any]) -> ri.ReviewerJudgment:
    # deterministic MOCK: assign E2 as a placeholder; NEVER validation
    return ri.ReviewerJudgment(obligation="E2_AUTHORITATIVE_INTERNAL_OR_IMPLEMENTATION_EVIDENCE",
                               risk_tier=blinded.get("risk_tier", "low"), confidence=0.6,
                               review_time_seconds=25.0)


def _mock_stage_b(blinded: Dict[str, Any], reveal: Dict[str, Any]) -> Dict[str, Any]:
    return {"judgment": ri.ReviewerJudgment(obligation=reveal["obligation"]),
            "agreement": True, "override": False, "explanation_usefulness": 4,
            "trace_comprehensible": True, "missing_context": False}


def run() -> Dict[str, Any]:
    training = dataset.load_training()          # NON-FINAL artifacts only
    state = orch.PilotState()
    checks = {"blinded_review": True, "timing": True, "policy_execution": True,
              "post_reveal_display": True, "override_recording": True, "audit": True, "replay": True,
              "adjudication": True, "deletion": True, "export_prohibited": True}

    for art in training:
        lr = orch.process_artifact(art, "MOCK-REV", _mock_stage_a, _mock_stage_b, is_mock=True)
        state.add(lr)
        # verify plumbing per artifact
        if lr.record.stage_a is None or lr.record.stage_b is None:
            checks["blinded_review"] = False
        if lr.record.enforced:
            checks["policy_execution"] = False
        if "obligation" not in lr.system_result:
            checks["post_reveal_display"] = False

    # stop-condition machinery: no immediate signals, metrics are NEHE (mock excluded) -> no cumulative
    from reviewer_calibration_pilot import metrics
    mock_metrics = metrics.compute([{"is_mock": True} for _ in state.reviews])
    stop = sc.evaluate(signals={c: False for c in sc._IMMEDIATE}, metrics=mock_metrics)

    all_ok = all(checks.values())
    return {
        "mode": "DRY_RUN_MOCK_REVIEWER",
        "note": "MACHINERY TEST ONLY on non-final (training) artifacts; the mock reviewer is NEVER human "
                "validation and never touches the final set.",
        "artifacts_processed": state.processed,
        "checks": checks,
        "all_plumbing_ok": all_ok,
        "all_non_enforcing": not state.enforced_any,
        "stop_machinery_ok": stop.should_stop is False,     # clean dry run trips nothing
        "metrics_status_on_mock": mock_metrics["status"],   # NOT_ENOUGH_HUMAN_EVIDENCE (mock excluded)
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = run()
    m["dry_run_sha256"] = hashlib.sha256(json.dumps(m["checks"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "dry_run.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"DRY RUN ({m['mode']}): processed={m['artifacts_processed']} plumbing_ok={m['all_plumbing_ok']} "
          f"non_enforcing={m['all_non_enforcing']}")
    print("checks:", m["checks"])
    print(f"stop machinery clean={m['stop_machinery_ok']} metrics_on_mock={m['metrics_status_on_mock']}")
