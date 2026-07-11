"""Tests for the B1.10 control-ext v3 pre-run EVIDENCE-FREEZE declaration.

Proves: every pinned input hash matches the live file; the declaration structure locks the approved v3-Qwen
inputs, the Llama/Gemma panel (no Claude/Mistral/Qwen judges), the 72-cell/216-rating structure, the five
primary statistics, and the interpretation ceiling; the runner ACCEPTS the declaration (its freeze gate passes,
blocking only on the absent real judge backend); and NO real judge is ever called. NO real model, NO network.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import json
import pathlib

import run_b1_10_control_ext as R

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
DECL = FROZEN / "b1_10_control_ext_v3_EVIDENCE_FREEZE_DECLARED.json"
V3_ITEMS = FROZEN / "b1_10_control_ext_items_v3_qwen.json"


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _decl():
    return json.loads(DECL.read_text())


def test_declaration_exists_and_flagged():
    d = _decl()
    assert d["evidence_freeze_declared"] is True
    assert d["provenance"]["evidence_freeze_declared"] is True
    assert d["experiment_identity"]["mode"] == "b1_10_control_ext"
    assert d["experiment_identity"]["mapping_era"] == "fidelity_bundle_v1"
    assert "B1.10" in d["experiment_identity"]["experiment_number"]


def test_every_pinned_hash_matches_live_file():
    d = _decl()
    for key, rec in d["pinned_input_hashes"].items():
        if "path" in rec:
            assert _sha(HERE / rec["path"]) == rec["sha256"], key
    # derived canonical block
    md = (HERE / "B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md").read_text()
    block = md.split("```")[1].strip("\n") + "\n"
    assert hashlib.sha256(block.encode()).hexdigest() == \
        d["pinned_input_hashes"]["approved_canonical_12_sentence_block"]["sha256"]


def test_pins_the_approved_v3_inputs():
    d = _decl()
    p = d["pinned_input_hashes"]
    assert p["rebuilt_v3_items_file"]["sha256"] == _sha(V3_ITEMS)
    assert p["approved_canonical_12_sentence_block"]["sha256"] == \
        "e0a1477ebaaf41df95b489b7547a895369f115d5231c424fc8598d4f598c3046"
    # required components all present
    for key in ("approved_context_source_file", "rebuilt_v3_items_file", "tier1_control_definitions",
                "tier2_control_definitions", "tier3_rendering_provenance_source", "v3_polarity_table",
                "active_bridge_manifest", "decomposer", "runner", "builder_v3", "judge_panel_specification",
                "control_hierarchy_specification", "packet_aware_audit_prereg", "packet_aware_audit_report",
                "dry_check_record"):
        assert key in p, key


def test_judge_configuration_locked():
    jc = _decl()["judge_configuration"]
    ids = [j["model_id"] for j in jc["panel"]]
    assert ids == ["meta-llama/Llama-3.1-8B-Instruct", "meta-llama/Meta-Llama-3-8B-Instruct",
                   "google/gemma-2-9b-it"]
    assert jc["identical_panel_across_all_tiers"] is True
    assert jc["no_claude_judges"] is True and jc["no_mistral_or_qwen_judges"] is True
    assert "0-6" in jc["rating_rubric"]
    assert "greedy" in jc["decoding"]


def test_run_structure_counts():
    rs = _decl()["run_structure"]
    assert rs["cells_per_judge"] == 72 and rs["n_judges"] == 3
    assert rs["expected_total_ratings"] == 216
    assert rs["no_missing_cell_imputation"] is True
    assert rs["items_file_for_real_run"] == "frozen/b1_10_control_ext_items_v3_qwen.json"


def test_primary_statistics_and_interpretation_lock():
    d = _decl()
    assert d["primary_statistics"] == ["specific_margin", "valence_margin", "generic_source_condition_margin",
                                       "increment_over_valence", "increment_over_source_condition"]
    il = d["interpretation_lock"]
    assert il["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    blob = json.dumps(il, ensure_ascii=False)
    for forbidden in ("no ontology claim", "no semantic-truth claim", "no Sanskrit-privilege claim",
                      "no generation-utility claim"):
        assert forbidden in blob
    # (the declaration deliberately NAMES GENUTILITY_*/ONTOLOGICAL_SIGNAL in its prohibition text;
    #  the "not emitted" guard belongs on run OUTPUT, tested in test_run_b1_10_control_ext.py)
    assert "individual-varṇa" in blob   # no single-varṇa attribution


def test_runner_accepts_declaration_but_blocks_on_real_judge():
    # freeze gate passes (declaration exists) -> the ONLY remaining block is the absent real judge backend
    try:
        R.run(mock=False, decl_path=DECL, judge=R.FakeJudge(), items_file=V3_ITEMS)
        assert False, "expected PermissionError"
    except PermissionError as e:
        msg = str(e)
        assert "real judge backend" in msg          # blocked on the judge...
        assert "declaration" not in msg              # ...NOT on the declaration (gate passed)


def test_missing_declaration_still_refused():
    try:
        R.run(mock=False, decl_path=None, judge=R.FakeJudge())
        assert False, "expected PermissionError"
    except PermissionError as e:
        assert "declaration" in str(e)


def test_no_real_judge_called():
    part = R.run(mock=True, items_file=V3_ITEMS)
    assert part["judge_is_real"] is False and part["mode"] == "MOCK"
