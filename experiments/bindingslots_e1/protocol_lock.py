#!/usr/bin/env python3
"""Mechanical protocol-lock verifier. Freezes source/dataset/split hashes, confirms the determinism and
leakage gates passed on dev, confirms the dev gates hold, and asserts that NO reserved seed/evaluation
has been run. Emits E1_PROTOCOL_LOCKED only when all conditions hold."""
from __future__ import annotations

import hashlib
import json
import pathlib

import task as T
import config as C

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE / "results"

SOURCE_FILES = ["task.py", "models.py", "engine.py", "gates.py", "config.py",
                "harness.py", "leakage.py", "run_dev.py", "run_dev_selection.py",
                "run_reserved.py", "protocol_lock.py"]

# Any of these existing means a reserved run already happened -> lock must refuse.
RESERVED_ARTIFACTS = ["reserved_eval.json", "aggregate_verdict.json", "per_seed_reserved.json"]


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def source_hashes():
    out = {}
    for f in SOURCE_FILES:
        p = HERE / f
        out[f] = _sha(p.read_bytes()) if p.exists() else None
    return out


def dataset_hashes():
    pools = T.identity_pools(C.POOL_SALT)
    train = C.build_train_episodes()
    dev = C.build_dev_eval()
    def h(obj):
        return _sha(json.dumps(obj, sort_keys=True).encode())
    return {
        "identity_pools": h({k: sorted(map(list, v)) for k, v in pools.items()}),
        "pool_sizes": {k: len(v) for k, v in pools.items()},
        "train_episodes": h(train),
        "dev_eval_splits": h({k: v for k, v in dev.items()}),
    }


def main():
    det = json.loads((RES / "determinism.json").read_text()) if (RES / "determinism.json").exists() else {}
    lk = json.loads((RES / "leakage_report.json").read_text()) if (RES / "leakage_report.json").exists() else {}
    dev = json.loads((RES / "dev_calibration.json").read_text()) if (RES / "dev_calibration.json").exists() else {}

    sel = json.loads((RES / "selection_result.json").read_text()) if (RES / "selection_result.json").exists() else {}
    determinism_ok = bool(det.get("determinism_ok"))
    leakage_ok = bool(lk.get("all_pass"))
    dev_pass = dev.get("dev_seeds_passing_all_primary", 0) >= 1
    selection_ok = bool(sel.get("winner_matches_frozen"))
    no_approval_required = all("APPROVAL_REQUIRED" not in str(v) for v in C.GATES.values())
    reserved_not_run = not any((RES / a).exists() for a in RESERVED_ARTIFACTS)

    if not reserved_not_run:
        result = "E1_PROTOCOL_NOT_READY"          # reserved artifacts present before lock
    elif not leakage_ok:
        result = "E1_SHORTCUT_OR_LEAKAGE_DETECTED"
    elif not determinism_ok:
        result = "E1_DETERMINISM_NOT_ESTABLISHED"
    elif determinism_ok and leakage_ok and dev_pass and selection_ok and no_approval_required:
        result = "E1_PROTOCOL_LOCKED"
    else:
        result = "E1_PROTOCOL_NOT_READY"

    out = {
        "schema": "bindingslots_e1/protocol_lock/v1",
        "result": result,
        "determinism_ok": determinism_ok,
        "leakage_all_pass": leakage_ok,
        "dev_seeds_passing_all_primary": dev.get("dev_seeds_passing_all_primary", 0),
        "selection_winner_matches_frozen": selection_ok,
        "mechanical_winner": sel.get("mechanical_winner"),
        "no_approval_required_remaining": no_approval_required,
        "reserved_not_run": reserved_not_run,
        "burned_seeds_not_final_cohort": C.BURNED_SEEDS,
        "reserved_seeds_declared": C.RESERVED_SEEDS,
        "frozen_gates": C.GATES,
        "frozen_config": {k: getattr(C, k) for k in ("D", "STEPS", "BATCH", "LR", "TAU",
                          "TRAIN_EPISODES", "TRAIN_NO_MATCH_FRAC", "TRAIN_SEED_FOR_EPISODES",
                          "POOL_SALT", "RESERVED_EVAL_N_PER_SPLIT", "RESERVED_SEEDS_REQUIRED_TO_PASS")},
        "source_hashes": source_hashes(),
        "dataset_hashes": dataset_hashes(),
    }
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / "protocol_lock.json"
    tmp = p.with_suffix(".json.tmp"); tmp.write_text(json.dumps(out, indent=2)); tmp.replace(p)
    print("PROTOCOL LOCK:", result, flush=True)
    print("  determinism_ok=%s leakage=%s dev_pass=%s no_approval_required=%s reserved_not_run=%s"
          % (determinism_ok, leakage_ok, dev_pass, no_approval_required, reserved_not_run), flush=True)
    return result


if __name__ == "__main__":
    main()
