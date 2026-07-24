"""Phases 5-6 tests: dataset partitions, sufficiency, disjointness, adversarial invariant targeting,
ground-truth independence and determinism."""
import ast, os
from minimal_evidence_policy import dataset as d, ground_truth as gt


def test_sufficient_and_partitioned():
    m = d.build()
    assert m["evidence_status"] == "SUFFICIENT"
    assert m["counts"]["DEVELOPMENT"] == 100
    assert m["counts"]["HELD_OUT_NATURAL"] == 250
    assert m["counts"]["ADVERSARIAL_INVARIANTS"] == 75
    assert m["counts"]["HUMAN_REVIEW_SET"] == 50


def test_excludes_all_prior_paths():
    prior = d._prior_paths()
    for i in d.load_partition("HELD_OUT_NATURAL"):
        assert i["source_path"] not in prior


def test_dev_heldout_disjoint():
    dev = {i["artifact_id"] for i in d.load_partition("DEVELOPMENT")}
    held = {i["artifact_id"] for i in d.load_partition("HELD_OUT_NATURAL")}
    assert dev.isdisjoint(held)


def test_adversarial_targets_invariants():
    invs = {i["target_invariant"] for i in d.load_partition("ADVERSARIAL_INVARIANTS")}
    assert {"INV-1", "INV-5", "INV-11", "INV-12"} <= invs


def test_ground_truth_independent_of_policy():
    src = open(os.path.join(os.path.dirname(gt.__file__), "ground_truth.py")).read()
    mods = [n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom)]
    assert not [m for m in mods if m and any(b in m for b in ("policy", "invariants", "modifiers"))]


def test_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(d.build()["partitions"], sort_keys=True).encode()).hexdigest()
    b = hashlib.sha256(json.dumps(d.build()["partitions"], sort_keys=True).encode()).hexdigest()
    assert a == b
