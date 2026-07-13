"""Validation for the symbolic-profile Stage-F preregistration. Deterministic; NO study, judges, raters, or models."""
import hashlib
import json
import pathlib

import b1_symbolic_profile_prereg as PR

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "symbolic_profile_prereg"
REQUIRED = ["closed_attribute_inventory.json", "word_eligibility_spec.json", "candidate_word_inventory.json",
            "packet_projection_spec.json", "and_composition_spec.json", "morphology_baseline_spec.json",
            "control_spec.json", "scoring_analysis_plan.json", "success_kill_criteria.json",
            "outcome_taxonomy.json", "heldout_split_procedure.json", "blind_profile_collection_protocol.json",
            "feasibility_report.json", "freeze_index.json"]


def test_all_artifacts_present():
    PR.build()
    for f in REQUIRED:
        assert (OUT / f).exists(), f


def test_deterministic():
    PR.build(); h1 = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in REQUIRED}
    PR.build(); h2 = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in REQUIRED}
    assert h1 == h2


def test_readiness_is_blocked_by_projection():
    idx = json.load(open(OUT / "freeze_index.json", encoding="utf-8"))
    assert idx["readiness_verdict"] == "PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION"
    assert idx["study_outcome_if_run_now"] == "STUDY_BLOCKED_BY_UNDEFINED_PROJECTION"


def test_domain_mismatch_is_the_evidence():
    fr = json.load(open(OUT / "feasibility_report.json", encoding="utf-8"))
    d = fr["domain_scan"]
    # packet is overwhelmingly tendency content; ~no genuine referent-attribute content
    assert d["n_tendency_terms"] >= 20
    assert d["n_referent_attribute_terms"] <= 8            # only incidental/metaphor/substring hits
    assert d["n_tendency_terms"] > 3 * d["n_referent_attribute_terms"]


def test_candidate_inventory_empty_by_design_not_invented():
    ci = json.load(open(OUT / "candidate_word_inventory.json", encoding="utf-8"))
    assert ci["n_eligible_established"] == 0 and ci["words"] == []          # no invented words


def test_projection_gate_blocks_and_and_operator_inert():
    fr = json.load(open(OUT / "feasibility_report.json", encoding="utf-8"))
    g = fr["gates"]
    assert g["deterministic_packet_projection_defined"]["pass"] is False
    assert g["and_operator_has_admissible_inputs"]["pass"] is False
    proj = json.load(open(OUT / "packet_projection_spec.json", encoding="utf-8"))
    assert "unconstrained LLM" in " ".join(proj["prohibited"])


def test_attribute_inventory_is_closed_and_externally_grounded():
    inv = json.load(open(OUT / "closed_attribute_inventory.json", encoding="utf-8"))
    assert inv["frozen"] is True and inv["n_dimensions"] == len(inv["dimensions"])
    assert any("Osgood" in s for s in inv["external_basis"])
    blob = json.dumps(inv).lower()
    assert "other" not in {d["name"] for d in inv["dimensions"]}            # no open 'other' field
    # no target word names leaked into the inventory
    for w in ("gaja", "aśva", "elephant", "horse"):
        assert w not in blob


def test_controls_include_profile_swap_and_morphology():
    c = json.load(open(OUT / "control_spec.json", encoding="utf-8"))["arms"]
    for arm in ("T", "X", "R", "S", "P", "G", "M", "D"):
        assert arm in c


def test_primary_contrast_and_success_are_relative():
    sp = json.load(open(OUT / "scoring_analysis_plan.json", encoding="utf-8"))
    assert "max(" in sp["primary_contrast"] and "Fit(T)" in sp["primary_contrast"]
    sk = json.load(open(OUT / "success_kill_criteria.json", encoding="utf-8"))
    assert "absolute fit" in sk["no_absolute_fit"]
    assert any("morphology" in c.lower() for c in sk["conjunctive_all_required"])


def test_does_not_modify_protected_artifacts():
    # this preregistration only READS the merged lexicon; the protected upstream artifacts are unchanged
    prot = {
        "sanskrit_stage1_parser.py": "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947",
        "frozen/varna_native_stage1_merged_v1.json": "af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96",
    }
    for rel, want in prot.items():
        assert hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == want, rel


def test_no_study_or_rater_in_source():
    src = (HERE / "b1_symbolic_profile_prereg.py").read_text()
    for banned in ("openai", "HfApi", "import torch", "transformers", "requests.post", "input(", "rater("):
        assert banned not in src
