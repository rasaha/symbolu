#!/usr/bin/env python3
"""Preserve BOTH the original preregistered classifier output and the amended output (§4).

Applies the original preregistered classifier (diagnosis_classify_preregistered_v1.py, verbatim copy
of commit 71fdcc84, sha256 db79114f…) AND the amended classifier (diagnosis_classify.py) to the SAME
committed per-seed measurements (results/per_seed_diagnosis.json), and writes
results/classifier_amendment_comparison.json recording both per-seed value-path classifications and
both aggregate verdicts, with both source hashes. Raw evidence is untouched; this only re-applies two
classifier versions to already-committed measurements, so the original output that the assembly step
overwrote is preserved transparently alongside the amended output.

Torch-free; deterministic; re-runnable in CI.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def build():
    orig = _load(HERE / "diagnosis_classify_preregistered_v1.py", "dc_orig")
    amended = _load(HERE / "diagnosis_classify.py", "dc_amended")
    per_seed = json.loads((HERE / "results" / "per_seed_diagnosis.json").read_text())["per_seed"]

    rows = []
    orig_diags, amended_diags = [], []
    for d in per_seed:
        m = d["measurements"]
        ov, _ = orig.value_path_diagnosis(m)
        av, _ = amended.value_path_diagnosis(m)
        rows.append({"arm": d["arm"], "seed": d["seed"],
                     "original_value_path": ov, "amended_value_path": av,
                     "quality_diagnosis": d["quality_diagnosis"], "changed": ov != av})
        orig_diags.append(orig.seed_diagnosis(d["arm"], d["seed"], m))
        amended_diags.append(amended.seed_diagnosis(d["arm"], d["seed"], m))

    return {
        "schema": "bindingslots_value_path_diagnosis/classifier_amendment_comparison/v1",
        "purpose": "preserve BOTH the original preregistered classifier output and the authorized "
                   "amended output on the identical committed measurements (§4)",
        "original_classifier": {
            "file": "diagnosis_classify_preregistered_v1.py",
            "source_commit": "71fdcc84",
            "sha256": _sha(HERE / "diagnosis_classify_preregistered_v1.py"),
            "value_path_rule": "gated on A2 LINEAR decodability",
            "aggregate_verdict": orig.aggregate_verdict(orig_diags),
        },
        "amended_classifier": {
            "file": "diagnosis_classify.py",
            "authorized_correction_commit": "f137653b",
            "sha256": _sha(HERE / "diagnosis_classify.py"),
            "value_path_rule": "query_recoverable = A4a-direct-read recovers OR A2 linearly decodable "
                               "(functional, per §9/§10/§11); STORAGE keeps explicit 'linearly decodable'",
            "aggregate_verdict": amended.aggregate_verdict(amended_diags),
        },
        "thresholds_unchanged": orig.FROZEN_CONSTANTS == amended.FROZEN_CONSTANTS,
        "seeds_whose_value_path_changed": [f"{r['arm']} s{r['seed']}" for r in rows if r["changed"]],
        "not_localized_still_reachable_under_amended":
            any(r["amended_value_path"] == "VALUE_PATH_NOT_LOCALIZED" for r in rows),
        "per_seed": rows,
    }


if __name__ == "__main__":
    doc = build()
    (HERE / "results" / "classifier_amendment_comparison.json").write_text(json.dumps(doc, indent=2) + "\n")
    print("original verdict:", doc["original_classifier"]["aggregate_verdict"])
    print("amended  verdict:", doc["amended_classifier"]["aggregate_verdict"])
    print("thresholds_unchanged:", doc["thresholds_unchanged"])
    print("changed seeds:", doc["seeds_whose_value_path_changed"])
    print("NOT_LOCALIZED still reachable:", doc["not_localized_still_reachable_under_amended"])
