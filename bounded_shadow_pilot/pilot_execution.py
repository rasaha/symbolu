"""Phase 19 - Frozen pilot execution.

The single scored run. Verifies the prior-artifact guard AND the eval freeze, runs the FULL frozen
natural set through the read-only wrapper exactly once, evaluates all six stop conditions on the full
set, and records the top-line pilot result. If any guard fails or any stop condition fires, the pilot
STOPS and records that outcome - it does not silently proceed.

Deterministic, read-only, non-enforcing. Writes eval_results/pilot_execution.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Dict

from bounded_shadow_pilot import (orchestrator_wrapper as ow, stop_conditions as sc,
                                  eval_freeze, verify_prior_artifacts)

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "natural_pilot_v1")
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")


def _load():
    corpus = json.load(open(os.path.join(_DATA, "corpus.json")))
    gt = json.load(open(os.path.join(_DATA, "ground_truth.json")))
    return corpus["artifacts"], {g["artifact_id"]: g for g in gt["labels"]}


def run() -> Dict[str, Any]:
    # 1. pre-run guards - both must hold before any scoring
    prior_ok = verify_prior_artifacts.verify()
    freeze_ok = eval_freeze.verify()
    guards_ok = prior_ok and freeze_ok

    artifacts, gts = _load()
    text_by_id = {a["artifact_id"]: a["text"] for a in artifacts}

    # 2. the single scored run over the full frozen set
    records = ow.run_batch(artifacts, gts)

    # 3. stop conditions on the FULL set
    stops = sc.evaluate_stops(records, text_by_id, ow.replay_signature)

    # 4. aggregate
    finals = Counter(r.final_shadow_disposition for r in records)
    native_actions = [r for r in records if r.action_derived]
    native_outcomes = Counter(r.native_action_outcome for r in native_actions)
    unsafe_permit = sum(1 for r in records
                        if r.gt_expected_class == "REVIEW" and r.final_shadow_disposition == "WOULD_ALLOW")
    all_non_enforcing = all(r.enforced is False for r in records)

    pilot_completed = guards_ok and not stops["should_stop"] and all_non_enforcing
    return {
        "corpus_id": "natural_pilot_v1",
        "n": len(records),
        "guards": {"prior_artifacts_intact": prior_ok, "eval_freeze_intact": freeze_ok,
                   "guards_ok": guards_ok},
        "final_distribution": dict(finals),
        "safety": {"unsafe_permit": unsafe_permit, "all_non_enforcing": all_non_enforcing},
        "native_actiongate": {"actions_derived": len(native_actions),
                              "native_outcome_distribution": dict(native_outcomes)},
        "stop_conditions": stops,
        "pilot_outcome": "COMPLETED_NO_STOP" if pilot_completed else "STOPPED",
        "pilot_completed_without_stop": pilot_completed,
    }


def freeze() -> Dict[str, Any]:
    m = run()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "pilot_execution.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"PILOT EXECUTION on n={m['n']}")
    print(f"guards: prior={m['guards']['prior_artifacts_intact']} "
          f"eval_freeze={m['guards']['eval_freeze_intact']}")
    print(f"final_distribution: {m['final_distribution']}")
    print(f"safety: unsafe_permit={m['safety']['unsafe_permit']} "
          f"non_enforcing={m['safety']['all_non_enforcing']}")
    print(f"native ActionGate: {m['native_actiongate']}")
    for c in m["stop_conditions"]["conditions"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['name']}")
    print(f"\nPILOT OUTCOME: {m['pilot_outcome']}")
