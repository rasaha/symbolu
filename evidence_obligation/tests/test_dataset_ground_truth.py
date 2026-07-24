"""Phase 6-7 tests: dataset partitions, sufficiency, determinism, adversarial safety labels, and
ground-truth independence from the component under test.
"""
import ast
import os

from evidence_obligation import dataset as d
from evidence_obligation import ground_truth as gt


def test_dataset_sufficient_and_partitioned():
    m = d.build()
    assert m["evidence_status"] == "SUFFICIENT"
    assert m["counts"]["DEVELOPMENT"] == 150
    assert m["counts"]["HELD_OUT_NATURAL"] == 250
    assert m["counts"]["ADVERSARIAL_OBLIGATION"] == 100


def test_partitions_disjoint_and_exclude_prior():
    prior = d._prior_paths()
    dev = {i["artifact_id"] for i in d.load_partition("DEVELOPMENT")}
    held = {i["artifact_id"] for i in d.load_partition("HELD_OUT_NATURAL")}
    assert dev.isdisjoint(held)                                  # dev and held-out disjoint
    for i in d.load_partition("HELD_OUT_NATURAL"):
        assert i["source_path"] not in prior                    # not in prior final set


def test_dataset_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(d.build()["partitions"], sort_keys=True).encode()).hexdigest()
    b = hashlib.sha256(json.dumps(d.build()["partitions"], sort_keys=True).encode()).hexdigest()
    assert a == b


def test_adversarial_never_labels_high_risk_no_gate():
    for i in d.load_partition("ADVERSARIAL_OBLIGATION"):
        # adversarial gold is always a real evidence obligation, never the no-gate class
        assert i["gold_obligation"] != "NO_FACTUAL_EVIDENCE_GATE"
        # every adversarial case names at least one unsafe obligation it must not receive
        assert len(i["unacceptable_obligations"]) >= 1


def test_ground_truth_is_independent_of_component():
    src = open(os.path.join(os.path.dirname(gt.__file__), "ground_truth.py")).read()
    tree = ast.parse(src)
    mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    banned = ("classifier", "policy", "obligations", "taxonomy", "source_role", "authority")
    assert not [m for m in mods if m and any(b in m for b in banned)]


def test_disguised_medical_opinion_gets_external_obligation():
    r = gt.adjudicate("In my opinion this drug completely cures the patient.", "generated_documentation")
    assert r["gold_obligation"] == "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED"
    assert "NO_FACTUAL_EVIDENCE_GATE" in r["unacceptable_obligations"]
