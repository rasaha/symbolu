#!/usr/bin/env python3
"""Deterministic trajectory-reproduction gate (§4). Compares a freshly reproduced run record against
the committed persistence raw_record at every available checkpoint, requiring EXACT equality on the
scientific fields (numerical tolerance is unnecessary: the runs are deterministic CPU fp32 and the
diagnostics never advance the training RNG, as proven on control runs). Timing (train_s) is excluded.
A run that fails the gate is classified INSTRUMENTED_REPRODUCTION_FAILED and its tensors must not be
used as scientific evidence.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PERS = REPO / "experiments" / "bindingslots_persistence"

# fields compared for EXACT equality; train_s (wall-clock) and loss_log lr echoes are excluded only
# where they are timing/formatting, not scientific signal.
COMPARE_KEYS = ["needle_by_dist", "ppl", "binding_by_k", "supersession", "source", "multihop",
                "trajectory", "ablation", "loss_log"]


def committed_record(arm, seed):
    p = PERS / "results" / "seeds" / arm / f"seed_{seed}" / "raw_record.json"
    return json.loads(p.read_text())


def _exact_equal(a, b, path=""):
    """Recursive exact structural equality; returns (ok, first_diff_path)."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False, f"{path}: key set differs {sorted(set(a)^set(b))}"
        for k in a:
            ok, d = _exact_equal(a[k], b[k], f"{path}.{k}")
            if not ok:
                return False, d
        return True, ""
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False, f"{path}: list len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            ok, d = _exact_equal(x, y, f"{path}[{i}]")
            if not ok:
                return False, d
        return True, ""
    if isinstance(a, float) or isinstance(b, float):
        # exact float equality (bit-for-bit determinism expected)
        return (a == b), (f"{path}: {a!r} != {b!r}" if a != b else "")
    return (a == b), (f"{path}: {a!r} != {b!r}" if a != b else "")


def gate(arm, seed, repro_record):
    committed = committed_record(arm, seed)
    diffs = []
    per_key = {}
    for k in COMPARE_KEYS:
        if k not in committed and k not in repro_record:
            per_key[k] = "absent_both"
            continue
        if (k in committed) != (k in repro_record):
            per_key[k] = "presence_mismatch"
            diffs.append(f"{k}: presence mismatch")
            continue
        ok, d = _exact_equal(repro_record[k], committed[k], path=k)
        per_key[k] = "exact" if ok else "MISMATCH"
        if not ok:
            diffs.append(d)
    passed = len(diffs) == 0
    return {
        "arm": arm, "seed": seed,
        "gate": "EXACT_EQUALITY",
        "passed": passed,
        "classification": "INSTRUMENTED_REPRODUCTION_ACCEPTED" if passed
                          else "INSTRUMENTED_REPRODUCTION_FAILED",
        "per_key": per_key,
        "first_diffs": diffs[:8],
        "committed_needle_by_dist": committed.get("needle_by_dist"),
        "repro_needle_by_dist": repro_record.get("needle_by_dist"),
        "committed_ppl": committed.get("ppl"),
        "repro_ppl": repro_record.get("ppl"),
    }
