#!/usr/bin/env python3
"""Freeze one deterministic presentation ORDER per evaluator (position-artifact mitigation, run-time only).

Each evaluator sees all 720 evaluator-facing items exactly once, in a per-evaluator deterministically shuffled
order derived from a frozen base seed + the evaluator_id. This changes ONLY the sequence in which items are shown;
it NEVER touches the candidate order inside a trial (that stays the frozen counterbalanced rotation). The order is
computed from opaque trial IDs alone — independent of arm, word, set, and correct answer. Manifests are hash-pinned
before response collection. ZERO model calls.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import random

import native_ws_runlib as R

HERE = pathlib.Path(__file__).resolve().parent
BASE_SEED = 20260907                                           # frozen base seed for presentation ordering


def eval_seed(base_seed: int, evaluator_id: str) -> int:
    return base_seed + int(hashlib.sha256(evaluator_id.encode("utf-8")).hexdigest()[:8], 16)


def build(manifest_path, trials_path, output_dir, base_seed):
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    man = R.load_manifest(manifest_path)
    trials = json.loads(pathlib.Path(trials_path).read_text(encoding="utf-8"))["trials"]
    all_ids = sorted(t["trial_id"] for t in trials)            # opaque IDs only; no answer/arm/word used

    index = {"base_seed": base_seed, "n_items": len(all_ids), "orders": {}}
    for ev in man["evaluators"]:
        eid = ev["evaluator_id"]
        seed = eval_seed(base_seed, eid)
        order = all_ids[:]
        random.Random(seed).shuffle(order)
        assert sorted(order) == all_ids and len(order) == len(set(order))   # permutation, each item once
        payload = {"evaluator_id": eid, "seed": seed, "n_items": len(order), "order": order}
        fp = out / f"{eid}_order.json"
        R.write_json_atomic(fp, payload)
        index["orders"][eid] = {"file": fp.name, "seed": seed, "n_items": len(order),
                                "sha256": R.sha256_file(fp)}
    R.write_json_atomic(out / "presentation_orders_index.json", index)
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--trials", default=str(R.TRIALS_PATH))
    ap.add_argument("--output-dir", default=str(HERE / "native_ws_presentation_orders"))
    ap.add_argument("--base-seed", type=int, default=BASE_SEED)
    a = ap.parse_args()
    idx = build(a.manifest, a.trials, a.output_dir, a.base_seed)
    print(json.dumps({"built_orders": list(idx["orders"].keys()),
                      "n_items": idx["n_items"], "base_seed": idx["base_seed"]}, indent=2))


if __name__ == "__main__":
    main()
