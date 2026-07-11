"""Tests for the focused v2 pre-run audit + dry run. Read-only recompute; NO network, NO model, NO evaluator run."""
import hashlib
import json
import pathlib

import b1_native_packet_prerun_audit_v2 as AUD
import b1_native_v2_dry_run as DRY

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "native_packet_prerun_audit_v2"


def test_position_meaningful_invariants_hold():
    f = AUD.build()
    p = f["1_position"]
    assert p["per_arm_uniform"] and p["per_word_uniform"] and p["per_set_uniform"] and p["same_valence_uniform"]
    # every order-independent position bias yields no T-vs-control edge
    assert p["order_independent_sim_max_delta"] == 0.0
    for a in ("X", "R", "G", "F"):
        assert p["T_profile_matches_each_control"][a] is True
    # the only nonzero policy is the order-dependent alternating artifact, far below the 0.15 success threshold
    assert 0.0 < p["order_dependent_alternating_delta"] < 0.15


def test_authoring_isolation_and_equivalence():
    f = AUD.build()
    iso = f["2_authoring_isolation"]
    assert all(iso.values())                       # input carries no identity; 17 rows; two poles; withheld list complete
    eq = f["3_equivalence"]
    assert eq["all_preserved"] and eq["r12_remediation_noted"] and eq["r15_no_surface_embellishment"]


def test_leakage_only_source_intrinsic():
    f = AUD.build()
    lk = f["4_leakage"]
    assert lk["exact_name_hits"] == []
    assert lk["n_paraphrase_added_cue"] == 0 and lk["n_unresolved"] == 0
    assert lk["only_exploitable_is_source_intrinsic"] is True


def test_opacity_no_reverse_mapping():
    f = AUD.build()
    o = f["5_opacity"]
    assert o["devanagari"] == 0 and o["iast_diacritic"] is False
    assert not any(o[k] for k in ("literal_arm_key", "target_word_field", "correct_label_field", "structured_id",
                                  "base_seq_field", "repeat_field", "rowid_token_present"))
    assert o["opaque_ids_only"] is True


def test_arm_mechanics_and_no_arm_classification():
    f = AUD.build()
    m = f["6_arm_mechanics"]
    for k in ("T_true", "X_derangement_no_fixed", "X_bijection", "S_order_only", "R_length_matched",
              "R_self_excluding", "F_metadata_only", "semantic_arms_uniform_format"):
        assert m[k] is True, k
    assert m["T_length_distinguishable_from_controls"] is False
    # semantic arms share identical length sets -> length cannot classify the arm
    ls = m["semantic_arm_length_sets"]
    assert ls["T"] == ls["X"] == ls["R"] == ls["G"]
    # frozen counts + repeat counts
    assert f["6_counts"] == {"A/F": 36, "A/G": 36, "A/R": 180, "A/S": 36, "A/T": 36, "A/X": 36,
                             "B/F": 36, "B/G": 36, "B/R": 180, "B/S": 36, "B/T": 36, "B/X": 36}
    assert set(f["6_repeat_counts"].values()) == {120}


def test_protocol_complete_no_placeholders():
    f = AUD.build()
    pr = f["7_protocol"]
    assert all(pr.values()), pr


def test_flagged_plan_precommitted():
    f = AUD.build()
    fp = f["9_flagged_plan"]
    assert fp["four_words"] and fp["caveat"] and fp["kept_in_primary"]
    assert fp["all_trial_primary"] and fp["sensitivity_excluding"] and fp["confusion"] and fp["concentration"]


def test_dry_run_all_branches_and_scoring():
    r = DRY.build()
    assert r["micro_all_pass"] is True
    assert r["sweeps"]["oracle_all_correct"]["overall_accuracy"] == 1.0
    assert all(abs(v - 1 / 6) < 1e-6 for v in r["sweeps"]["always_W1"]["per_arm_accuracy"].values())
    assert r["sweeps"]["all_invalid"]["overall_accuracy"] == 0.0
    assert all(r["structural_guarantees"].values())
    assert r["dry_run_pass"] is True


def test_deterministic_outputs():
    AUD.build(); h1 = hashlib.sha256((OUT / "audit_findings_v2.json").read_bytes()).hexdigest()
    AUD.build(); h2 = hashlib.sha256((OUT / "audit_findings_v2.json").read_bytes()).hexdigest()
    assert h1 == h2
    DRY.build(); d1 = hashlib.sha256((OUT / "dry_run_record.json").read_bytes()).hexdigest()
    DRY.build(); d2 = hashlib.sha256((OUT / "dry_run_record.json").read_bytes()).hexdigest()
    assert d1 == d2


def test_v2_frozen_and_protected_hashes_unchanged():
    # v2 freeze self-consistent
    v2 = HERE / "native_word_specificity_packets_v2"
    fi = json.load(open(v2 / "packet_freeze_index.json", encoding="utf-8"))
    for f, h in fi["frozen_hashes"].items():
        assert hashlib.sha256((v2 / f).read_bytes()).hexdigest() == h, f
    # protected upstream + v1 packet freeze self-consistent
    prot = {
        "sanskrit_stage1_parser.py": "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947",
        "frozen/varna_native_stage1_merged_v1.json": "af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96",
        "b1_native_gate_g0.py": "4bcc8838c924543ba56ab21f484e9864e93faca12ca78ffd655c76b0a5f59d7f",
        "native_word_specificity_prereg/freeze_index.json": "155baad28dfd656562a66b60fd0a7f3e9aa1fa029d32ebfb643483ec65da5632",
    }
    for rel, want in prot.items():
        assert hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == want, rel
    v1 = HERE / "native_word_specificity_packets"
    fi1 = json.load(open(v1 / "packet_freeze_index.json", encoding="utf-8"))
    for f, h in fi1["frozen_hashes"].items():
        assert hashlib.sha256((v1 / f).read_bytes()).hexdigest() == h, f
