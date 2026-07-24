"""Phases 4-5 tests: training/final separation, sufficiency, blind final set, trap coverage, determinism."""
from reviewer_calibration_pilot import dataset as d


def test_sufficient_and_counts():
    m = d.build()
    assert m["evidence_status"] == "SUFFICIENT"
    assert m["counts"]["training"] == 20
    assert m["counts"]["final_review"] >= 60


def test_training_final_disjoint():
    tr = {i["artifact_id"] for i in d.load_training()}
    fn = {i["artifact_id"] for i in d.load_final()}
    assert tr.isdisjoint(fn)


def test_final_excludes_all_prior():
    prior = d._prior_paths()
    for i in d.load_final():
        if not i.get("synthetic"):
            assert i["source_path"] not in prior


def test_final_is_blind_no_reviewer_gold():
    # natural final items store metadata only, never a reviewer gold obligation
    for i in d.load_final():
        if not i.get("synthetic"):
            assert "gold_obligation" not in i


def test_training_is_labelled():
    for i in d.load_training():
        assert "gold_obligation" in i


def test_traps_present_both_sets():
    assert any(i.get("synthetic") for i in d.load_training())
    assert sum(1 for i in d.load_final() if i.get("synthetic")) >= 8


def test_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(d.build()["final_review"], sort_keys=True).encode()).hexdigest()
    b = hashlib.sha256(json.dumps(d.build()["final_review"], sort_keys=True).encode()).hexdigest()
    assert a == b
