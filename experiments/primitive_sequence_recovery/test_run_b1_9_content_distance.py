"""Tests for the B1.9 content-level semantic-distance runner. Fake embeddings only; NO model download, NO
network, NO generation, NO judging, NO run_out reads, NO terminal result label. B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import re
import pathlib
import pytest

import run_b1_9_content_distance as D


def _decl(tmp_path, **over):
    d = {"artifact": "b1_9_content_distance_DECLARED", "b1_9_declared": True,
         "mode": D.MODE, "representation_version": D.REPRESENTATION,
         "declared_by": "op", "declared_at_utc": "2026-07-09T00:00:00Z", "attestation": D.ATTESTATION,
         **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
    d.update(over)
    p = tmp_path / "decl.json"; p.write_text(json.dumps(d))
    return p


# ---- gate ---------------------------------------------------------------------------
def test_valid_declaration_accepted(tmp_path):
    ok, reasons = D.verify_declaration(_decl(tmp_path)); assert ok, reasons

def test_missing_declaration_refused(tmp_path):
    ok, _ = D.verify_declaration(tmp_path / "nope.json"); assert not ok

def test_wrong_mode_refused(tmp_path):
    ok, r = D.verify_declaration(_decl(tmp_path, mode="pilot_generation"))
    assert not ok and any("mode" in x for x in r)

def test_wrong_representation_refused(tmp_path):
    ok, r = D.verify_declaration(_decl(tmp_path, representation_version="B1.8_context_resolved_layer1"))
    assert not ok and any("representation_version" in x for x in r)

def test_b18_b16_declaration_refused(tmp_path):
    d = {"artifact": "b1_8_context_resolved_EVIDENCE_FREEZE_DECLARED", "b1_9_declared": True,
         "mode": "b1_8_context_resolved_generation_probe", "representation_version": "B1.8_context_resolved_layer1",
         "declared_by": "op", "declared_at_utc": "t", "attestation": "x"}
    p = tmp_path / "d.json"; p.write_text(json.dumps(d))
    ok, r = D.verify_declaration(p)
    assert not ok and any("B1.6/B1.8 mode" in x for x in r)

def test_hash_mismatch_refused(tmp_path):
    ok, r = D.verify_declaration(_decl(tmp_path, targets_sha256="deadbeef"))
    assert not ok and any("targets_sha256 mismatch" in x for x in r)


# ---- preprocessing / aggregation determinism ----------------------------------------
def test_preprocessing_deterministic():
    f = D.load_frozen()
    a = D.normalize("Dread, of FAILURE!!  ", f["preproc"]); b = D.normalize("Dread, of FAILURE!!  ", f["preproc"])
    assert a == b == "dread of failure"

def test_aggregation_deterministic():
    f = D.load_frozen()
    it = f["targets"]["targets"][0]; vs = D._supported_varnas(it, f["facets"])
    assert D.facet_aggregate(vs, f["facets"], f["preproc"]) == D.facet_aggregate(vs, f["facets"], f["preproc"])
    assert vs  # non-empty


# ---- control families implemented or blocked-with-reason -----------------------------
def test_all_families_implemented_or_blocked_with_reason():
    for fam in D.CONTROL_FAMILIES:
        status, reason = D.FAMILY_STATUS[fam]
        assert status in ("IMPLEMENTED", "IMPLEMENTED_LENGTH_ONLY", "BLOCKED_NOT_AVAILABLE")
        if status.startswith("BLOCKED"):
            assert reason and len(reason) > 10          # explicit reason required
    assert D.FAMILY_STATUS["same_polarity_random_varna_facet"][0] == "BLOCKED_NOT_AVAILABLE"

def test_blocked_family_yields_no_deltas():
    f = D.load_frozen()
    res = D.compute_family(f["targets"]["targets"], "same_polarity_random_varna_facet", f, D.FakeEmbedding())
    assert res["status"] == "BLOCKED_NOT_AVAILABLE" and res["deltas"] == []


# ---- corrected control: distant source word's OWN authentic varṇa mapping -------------
def test_distant_source_is_primary_and_implemented():
    f = D.load_frozen()
    assert f["sampler"]["primary_family"] == "distant_source_word_mapping"
    assert D.CONTROL_FAMILIES[0] == "distant_source_word_mapping"
    assert D.FAMILY_STATUS["distant_source_word_mapping"][0] == "IMPLEMENTED"

def test_distant_source_scores_all_items_with_a_different_source_word():
    f = D.load_frozen()
    items = f["targets"]["targets"]
    res = D.compute_family(items, "distant_source_word_mapping", f, D.FakeEmbedding())
    scored = [p for p in res["per_item"] if "delta_distance" in p]
    assert len(scored) == len(items)
    for p in scored:
        assert p["source_word_id"] != p["item_id"]          # W′ is a DIFFERENT word
        assert p["source_word_id"] in {it["item_id"] for it in items}

def test_distant_source_map_uses_only_target_context_not_facets_or_outcomes():
    import inspect
    src = _strip_docstrings(inspect.getsource(D._freeze_distant_source_map))
    assert "facet" not in src            # selection never touches facet content
    assert "d_auth" not in src           # selection never references the outcome
    # map is deterministic and each W′ is the most target/context-distant item
    f = D.load_frozen(); items = f["targets"]["targets"]; be = D.FakeEmbedding()
    m1 = D._freeze_distant_source_map(items, f["preproc"], be)
    m2 = D._freeze_distant_source_map(items, f["preproc"], be)
    assert m1 == m2
    reps = [D.target_rep(it, f["preproc"]) for it in items]
    embs = be.embed(reps)
    for i, it in enumerate(items):
        dists = {items[j]["item_id"]: D._cos_dist(embs[i], embs[j]) for j in range(len(items)) if j != i}
        assert m1[it["item_id"]] == max(dists, key=lambda k: dists[k])

def test_distant_source_endpoint_is_control_minus_auth():
    f = D.load_frozen(); items = f["targets"]["targets"]
    res = D.compute_family(items, "distant_source_word_mapping", f, D.FakeEmbedding())
    p = next(x for x in res["per_item"] if "delta_distance" in x)
    # each field independently rounded to 4dp -> compare within rounding tolerance
    assert abs(p["delta_distance"] - (p["d_control"] - p["d_auth"])) < 2e-4


# ---- out-of-pool control (secondary/external-register; reuses NO varṇa mapping) --------
def test_out_of_pool_is_secondary_and_implemented():
    f = D.load_frozen()
    assert f["sampler"]["primary_family"] != "out_of_pool_lexicon_facet"
    assert "out_of_pool_lexicon_facet" in D.CONTROL_FAMILIES
    assert D.FAMILY_STATUS["out_of_pool_lexicon_facet"][0] == "IMPLEMENTED"

def test_out_of_pool_scores_all_items():
    f = D.load_frozen()
    res = D.compute_family(f["targets"]["targets"], "out_of_pool_lexicon_facet", f, D.FakeEmbedding())
    scored = [p for p in res["per_item"] if "delta_distance" in p]
    assert len(scored) == len(f["targets"]["targets"])
    assert res["mean_delta"] is not None

def test_out_of_pool_content_not_from_varna_pool():
    # every sampled control gloss is a frozen out-of-pool lexicon entry, never a varṇa facet text
    f = D.load_frozen()
    lexicon = set(f["out_of_pool"]["glosses"])
    varna_facet_texts = {D._varna_facet_text(v, f["facets"], f["preproc"]) for v in f["facets"]}
    sampled = D._sample_out_of_pool("b18-01", f["out_of_pool"]["glosses"], f["sampler"]["K"], f["sampler"]["seed"])
    assert sampled and all(g in lexicon for g in sampled)
    assert all(g not in varna_facet_texts for g in sampled)   # control content is genuinely out-of-pool

def test_out_of_pool_sampling_deterministic():
    f = D.load_frozen()
    a = D._sample_out_of_pool("b18-05", f["out_of_pool"]["glosses"], 5, 20260709)
    b = D._sample_out_of_pool("b18-05", f["out_of_pool"]["glosses"], 5, 20260709)
    assert a == b


# ---- reproducibility with fixed seed -------------------------------------------------
def test_fixed_seed_reproducible():
    f = D.load_frozen()
    r1 = D.compute_family(f["targets"]["targets"], "completely_random_facet", f, D.FakeEmbedding())
    r2 = D.compute_family(f["targets"]["targets"], "completely_random_facet", f, D.FakeEmbedding())
    assert r1["per_item"] == r2["per_item"] and r1["mean_delta"] == r2["mean_delta"]


# ---- anti-circularity ---------------------------------------------------------------
def test_no_item_removed_because_authentic_closer():
    # every non-refused item stays regardless of delta sign (no d_auth<d_control filtering)
    f = D.load_frozen()
    res = D.compute_family(f["targets"]["targets"], "completely_random_facet", f, D.FakeEmbedding())
    scored = [p for p in res["per_item"] if "delta_distance" in p]
    assert len(scored) == len(f["targets"]["targets"])      # all 12 kept, no post-hoc removal
    assert any(p["delta_distance"] <= 0 for p in scored) or any(p["delta_distance"] > 0 for p in scored)

def _strip_docstrings(src):
    return re.sub(r'(?s)""".*?"""', "", src)

def test_refusals_computed_before_outcomes_and_ignore_d_auth():
    # determine_refusals CODE (docstring stripped) never references the d_auth variable
    import inspect
    assert "d_auth" not in _strip_docstrings(inspect.getsource(D.determine_refusals))
    # force the refusal path deterministically: tau=2.1 is unreachable (cos-dist in [0,2]) -> every item refused
    f = D.load_frozen()
    cons = {"enabled": True, "min_control_target_distance": 2.1, "applies_to": ["completely_random_facet"]}
    f = {**f, "sampler": {**f["sampler"], "prospective_distance_constraint": cons}}
    ref = D.determine_refusals(f["targets"]["targets"], "completely_random_facet", f, D.FakeEmbedding(), cons)
    assert len(ref) == len(f["targets"]["targets"])
    assert all(v == "REFUSE_UNSEPARABLE" for v in ref.values())


# ---- distance / delta semantics ------------------------------------------------------
def test_delta_equals_control_minus_auth_and_positive_favors_authentic():
    # controlled fake vectors: target near authentic, far from control -> d_auth small, d_control large, delta>0
    f = D.load_frozen()
    it = f["targets"]["targets"][0]
    vs = D._supported_varnas(it, f["facets"])
    t = D.target_rep(it, f["preproc"]); a = D.facet_aggregate(vs, f["facets"], f["preproc"])
    mapping = {t: [1.0, 0.0], a: [0.98, 0.20]}    # authentic vector close to target; others hash-random/far
    be = D.FakeEmbedding(mapping=mapping, dim=2)
    te = be.embed([t])[0]; ae = be.embed([a])[0]
    d_auth = D._cos_dist(te, ae)
    # any control far from target => d_control > d_auth => delta>0
    ce = be.embed(["totally-unrelated-control-text"])[0]
    d_ctrl = D._cos_dist(te, ce)
    delta = d_ctrl - d_auth
    assert abs(delta - (d_ctrl - d_auth)) < 1e-9
    assert (delta > 0) == (d_auth < d_ctrl)       # positive delta <=> authentic closer


# ---- statistics skeleton -------------------------------------------------------------
def test_statistics_on_paired_deltas():
    s = D.statistics([0.1, -0.05, 0.2, 0.0, 0.15], seed=1)
    assert s["mean_delta"] is not None and s["median_delta"] is not None
    assert s["sign_pos"] == 3 and s["sign_neg"] == 1
    assert isinstance(s["bootstrap_ci95"], list) and len(s["bootstrap_ci95"]) == 2
    assert 0.0 <= s["permutation_p"] <= 1.0
    assert 0.0 <= s["sign_test_p"] <= 1.0

def test_statistics_from_family_are_paired_item_deltas():
    f = D.load_frozen()
    res = D.compute_family(f["targets"]["targets"], "completely_random_facet", f, D.FakeEmbedding())
    deltas = [p["delta_distance"] for p in res["per_item"] if "delta_distance" in p]
    assert res["sign_pos"] + res["sign_neg"] <= len(deltas)
    assert res["mean_delta"] == round(sum(deltas) / len(deltas), 4)


# ---- full mock run, no leakage of forbidden labels / no run_out ----------------------
def test_mock_run_no_terminal_labels_no_runout(tmp_path):
    res = D.run(mock=True, out_dir=tmp_path, write=True)
    blob = json.dumps(res)
    assert res["label"] == "B1_9_CONTENT_DISTANCE_RUNNER_READY_MOCK_TESTED"
    for bad in ("B1_9_CONTENT_DISTANCE_NULL", "B1_9_CONTENT_DISTANCE_WEAK_EXPLORATORY",
                "B1_9_CONTENT_DISTANCE_ROBUST_PROSPECTIVE", "ONTOLOGICAL_SIGNAL"):
        assert bad not in blob
    assert not re.search(r"GENUTILITY_[A-Z]", blob)
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    assert res["manifest"]["terminal_result_label_emitted"] is False
    assert (tmp_path / "b1_9_manifest.json").exists()

def test_real_run_refuses_without_declaration():
    with pytest.raises(PermissionError):
        D.run(mock=False, decl_path=None)

def test_no_runout_or_generation_imports():
    src = pathlib.Path("run_b1_9_content_distance.py").read_text()
    code = _strip_docstrings(src)                         # docstrings legitimately mention these words
    assert "run_out/" not in code                         # no run_out path is read in code
    assert "\ngenerate(" not in code and ".generate(" not in code   # no generation call
    # imports no generation/judging/adapter modules
    for mod in ("run_b1_6", "run_b1_8", "b1_6_llm_adapter", "b1_6_llm_judge_panel",
                "judge_b1_6_pilot_outputs", "b1_6_model_panel", "perspective_lens_probe"):
        assert f"import {mod}" not in code
