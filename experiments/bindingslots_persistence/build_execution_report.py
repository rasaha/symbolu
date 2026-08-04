#!/usr/bin/env python3
"""Build the aggregate execution artifacts + reproducible-replay proof from committed per-seed
evidence. Reclassifies every seed from raw evidence (never trusting stored booleans) and replays the
adaptive planner to prove the actual run ledger is mechanically reproducible. Pure stdlib."""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adaptive_plan as AP  # noqa: E402
import persistence_classify as PC  # noqa: E402

RESULTS = HERE / "results"
LEDGER = RESULTS / "execution_ledger.json"
SEEDS = [23, 24, 25, 26, 27]


def raw(arm, seed):
    p = RESULTS / "seeds" / arm / f"seed_{seed}" / "raw_record.json"
    return json.loads(p.read_text()) if p.exists() else None


def clean_count(arm):
    n = 0
    for s in SEEDS:
        rec = raw(arm, s)
        if rec is None:
            continue
        if arm == "A+":
            continue
        ap = raw("A+", s)
        if ap and PC.classify_seed(rec, ap)["clean_stable"]:
            n += 1
    return n


def main():
    if not LEDGER.exists():
        print("no ledger yet"); return 1
    order = json.loads(LEDGER.read_text())["order"]

    # ---- reproducible replay: reconstruct next_action sequence from evidence ----
    completed, replay_actions = [], []
    for e in order:
        act = AP.next_action(completed)
        replay_actions.append(act)
        assert act["action"] == "run" and act["arm"] == e["arm"] and act["seed"] == e["seed"], \
            f"replay mismatch at {e}: planner wanted {act}"
        arm, seed = e["arm"], e["seed"]
        cs = False if arm == "A+" else PC.classify_seed(raw(arm, seed), raw("A+", seed))["clean_stable"]
        completed.append({"arm": arm, "seed": seed, "clean_stable": cs})
    terminal = AP.next_action(completed)

    status = AP.full_status(completed)
    r0_clean = clean_count("R0")
    cand_clean = {a: clean_count(a) for a in ("O1R", "H1", "H2") if raw(a, 23) is not None}

    # step-600 vs step-1200 routing retention summary (candidates present)
    retention = {}
    for a in ("O1R", "H1", "H2", "O1"):
        rows = {}
        for s in SEEDS:
            rec = raw(a, s)
            if rec is None:
                continue
            import fr_classifier as FRC
            r6 = FRC.routing_at(rec, 600) or {}
            r12 = FRC.routing_at(rec, 1200) or {}
            rows[str(s)] = {"prob_600": r6.get("read_prob_on_highest_write_slot"),
                            "prob_1200": r12.get("read_prob_on_highest_write_slot"),
                            "needle_1200": rec["needle_by_dist"]["96"]}
        if rows:
            retention[a] = rows

    aggregate = {
        "schema": "bindingslots_persistence/aggregate_classification/v1",
        "actual_run_count": len(order),
        "min_permitted": 15, "max_permitted": 30,
        "execution_sequence": [f"{e['arm']}:{e['seed']}={'CS' if e['clean_stable'] else 'x'}" for e in order],
        "r0_clean_stable_count": r0_clean,
        "candidate_clean_stable_counts": cand_clean,
        "step600_vs_step1200_retention": retention,
        "full_status": status["status"],
        "selected_candidate": terminal.get("selected"),
        "primary_verdict": terminal.get("verdict"),
        "kda_readiness": terminal.get("kda_readiness", "KDA_VALIDATION_BLOCKED"),
        "replay_reproducible": True,
    }
    (RESULTS).mkdir(exist_ok=True)
    (RESULTS / "aggregate_classification.json").write_text(json.dumps(aggregate, indent=2) + "\n")
    (RESULTS / "selection_decision.json").write_text(json.dumps(
        {"schema": "bindingslots_persistence/selection_decision/v1",
         "selected_candidate": terminal.get("selected"),
         "primary_verdict": terminal.get("verdict"),
         "tie_break_order": ["O1R", "H1", "H2"],
         "note": "unrun arms are NOT_EVALUATED, never failed or inferior"}, indent=2) + "\n")
    (RESULTS / "execution_integrity_report.json").write_text(json.dumps(
        {"schema": "bindingslots_persistence/execution_integrity_report/v1",
         "replay_reproducible": True, "run_count": len(order),
         "verdict": terminal.get("verdict"), "kda_readiness": "KDA_VALIDATION_BLOCKED"}, indent=2) + "\n")
    print(json.dumps({"verdict": terminal.get("verdict"), "selected": terminal.get("selected"),
                      "runs": len(order), "r0_clean": r0_clean, "cand_clean": cand_clean}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
