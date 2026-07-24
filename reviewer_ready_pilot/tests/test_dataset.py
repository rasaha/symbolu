"""M4 tests - training + final review datasets (Phases 6 & 8)."""
import json
import os

from reviewer_ready_pilot import dataset

_PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_build_sufficient_and_counts():
    m = dataset.build()
    assert m["evidence_status"] == "SUFFICIENT", m["evidence_status"]
    c = m["counts"]
    assert 20 <= c["training"] <= 30, c
    assert c["training_natural"] == dataset.NATURAL_TRAINING
    assert c["final_natural"] >= dataset.MIN_FINAL, c


def test_training_has_revealed_labels():
    from reviewer_ready_pilot.qualification import short_level
    tr = dataset.build()["training"]
    for it in tr:
        assert short_level(it.get("gold_obligation")) in {"E0", "E1", "E2", "E3", "E4", "ER"}, it
        assert "gold_explanation" in it


def test_final_is_blind_no_gold():
    fn = dataset.build()["final_review"]
    for it in fn:
        assert "gold_obligation" not in it, "final set must not reveal the system result"
        assert "gold_explanation" not in it


def test_training_and_final_disjoint():
    m = dataset.build()
    tr_ids = {i["artifact_id"] for i in m["training"]}
    fn_ids = {i["artifact_id"] for i in m["final_review"]}
    assert tr_ids.isdisjoint(fn_ids)
    tr_paths = {i["source_path"] for i in m["training"] if not i.get("synthetic")}
    fn_paths = {i["source_path"] for i in m["final_review"] if not i.get("synthetic")}
    assert tr_paths.isdisjoint(fn_paths)


def test_excludes_all_prior_source_paths():
    prior = dataset._prior_paths()
    assert len(prior) >= 600, f"expected the full prior exclusion set, got {len(prior)}"
    m = dataset.build()
    for coll in (m["training"], m["final_review"]):
        for it in coll:
            if not it.get("synthetic"):
                assert it["source_path"] not in prior, it["source_path"]


def test_traps_flagged_synthetic_and_cover_all_families():
    m = dataset.build()
    fam = {i["trap_type"] for i in m["final_review"] if i.get("source_kind") == "trap"}
    assert fam == {t[0] for t in dataset._TRAPS}
    edge = {i["edge_type"] for i in m["final_review"] if i.get("source_kind") == "edge_case"}
    assert edge == {e[0] for e in dataset._EDGE}
    for it in m["training"] + m["final_review"]:
        if it.get("source_kind") in ("trap", "edge_case"):
            assert it["synthetic"] is True


def test_freeze_writes_files_and_manifest():
    dataset.freeze()
    assert os.path.exists(os.path.join(_PKG, "data", "training_v1", "training.json"))
    assert os.path.exists(os.path.join(_PKG, "data", "final_review_v1", "final_review.json"))
    manifest = json.load(open(os.path.join(_PKG, "data", "manifest.json")))
    assert manifest["evidence_status"] == "SUFFICIENT"
    assert "training_sha256" in manifest and "final_sha256" in manifest
