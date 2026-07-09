"""Tests for the B1.7 perspective-lens controllability probe. Fake adapters only; NO model, NO network,
NO real generation/guessing, NO unblinding beyond the aggregation step. B1.4b' stays NULL_RETURN_BOTTOM."""
import json
import hashlib
import pathlib
import re
import pytest

import perspective_lens_probe as PL
import b1_6_llm_adapter as A


LEX = PL.load_sphere_varnas()
TARGETS = json.loads(PL.TARGETS_FILE.read_text())


# ---- sphere facets + derangement --------------------------------------------------------
def test_facets_pull_target_plane_glosses():
    f_phys = PL.varna_sphere_facets(["ka"], "physical", LEX)
    f_ment = PL.varna_sphere_facets(["ka"], "mental", LEX)
    assert f_phys and f_ment and f_phys != f_ment            # different plane -> different gloss


def test_derangement_no_fixed_points():
    keys = sorted(LEX.keys())
    d = PL._derangement(keys, seed=20260709)
    assert set(d.keys()) == set(keys)
    assert all(d[k] != k for k in keys)                      # no varna maps to itself


# ---- prompt rendering -------------------------------------------------------------------
def test_render_arms_differ():
    varnas = ["ra", "va", "ra"]
    plain = PL.render_prompt("PLAIN_SPHERE_INSTRUCTION", "river", varnas, "mental", LEX)
    varna = PL.render_prompt("VARNA_SPHERE_LENS", "river", varnas, "mental", LEX)
    nolens = PL.render_prompt("NO_LENS_BASELINE", "river", varnas, None, LEX)
    assert "mental" in plain and "facets of experience" not in plain      # plain names plane, no facets
    assert "facets of experience" in varna and "mental" in varna          # varna names plane AND gives facets
    assert "plane" not in nolens.lower().split("format")[0]                # no target plane in no-lens head


def test_randomized_differs_from_varna():
    rm = PL._derangement(sorted(LEX.keys()), 20260709)
    varnas = ["ka", "ra", "ma"]
    real = PL.render_prompt("VARNA_SPHERE_LENS", "x", varnas, "physical", LEX, rm)
    rand = PL.render_prompt("RANDOMIZED_VARNA_SPHERE", "x", varnas, "physical", LEX, rm)
    assert real != rand                                       # shuffled glosses -> different scaffold


def test_lens_arm_requires_valid_plane():
    with pytest.raises(ValueError):
        PL.render_prompt("VARNA_SPHERE_LENS", "x", ["ka"], "bogus", LEX)


# ---- records + blinding -----------------------------------------------------------------
def test_build_records_count():
    recs = PL.build_records(TARGETS, LEX, 20260709)
    # per word: 3 lens arms x 4 lenses + 1 no-lens = 13; x 8 words = 104
    assert len(recs) == 13 * TARGETS["n_targets"]
    assert {r["blinded_output_id"] for r in recs}.__len__() == len(recs)   # unique ids


def test_judge_visible_is_blind_and_b16_compatible():
    recs = PL.build_records(TARGETS, LEX, 20260709)
    pkg = PL.make_judge_visible(recs[0], "Title: t\nInterpretation: a b c\nPractical reflection:\n- x\n- y\nCaution: limited.")
    assert set(pkg.keys()) == PL.ALLOWED_JV_KEYS
    assert "arm" not in pkg and "target_sphere" not in pkg and "native_plane" not in pkg


def test_judge_visible_refuses_method_leak():
    recs = PL.build_records(TARGETS, LEX, 20260709)
    with pytest.raises(ValueError):
        PL.make_judge_visible(recs[0], "this uses the KCPR varna prana-shakti tattva")


def test_plain_english_not_flagged_as_leak():
    assert PL.leaked("a warm reading of the physical and mental planes") == []


# ---- gated mock run ---------------------------------------------------------------------
def test_mock_run_blind_and_no_leak(tmp_path):
    res = PL.run(mock=True, gen_code="M1", out_dir=tmp_path, write=True)
    m = res["manifest"]
    assert m["mode"] == "MOCK" and m["n_success"] == 13 * TARGETS["n_targets"] and m["n_failures"] == 0
    assert m["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM" and m["unblinded"] is False
    # blind file present, no arm/plane/varna leak anywhere
    jv = (tmp_path / "panel_judge_visible_outputs.jsonl").read_text()
    assert not re.search(r"VARNA_SPHERE|NO_LENS|true_arm|target_sphere|native_plane", jv)
    assert (tmp_path / "panel_hidden_lens_metadata.json").exists()


def test_real_run_refuses_without_declaration():
    with pytest.raises(PermissionError):
        PL.run(mock=False, adapter=object(), decl_path=None)


def test_gate_refuses_bad_attestation(tmp_path):
    decl = {"artifact": "b1_7_perspective_lens_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
            "mode": PL.MODE, "targets_sha256": "x", "sphere_lexicon_sha256": "y",
            "declared_by": "op", "declared_at_utc": "t", "attestation": "WRONG"}
    p = tmp_path / "d.json"; p.write_text(json.dumps(decl))
    ok, reasons = PL.verify_freeze_gate(p)
    assert not ok and any("attestation" in r for r in reasons)


def test_gate_accepts_valid_declaration(tmp_path):
    def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    decl = {"artifact": "b1_7_perspective_lens_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
            "mode": PL.MODE, "targets_sha256": sha(PL.TARGETS_FILE),
            "sphere_lexicon_sha256": sha(PL.SPHERE_LEXICON_FILE), "declared_by": "op",
            "declared_at_utc": "t", "attestation": PL.ATTESTATION}
    p = tmp_path / "d.json"; p.write_text(json.dumps(decl))
    ok, reasons = PL.verify_freeze_gate(p)
    assert ok, reasons


# ---- controllability --------------------------------------------------------------------
def test_parse_guess():
    assert PL.parse_guess("mental") == "mental"
    assert PL.parse_guess("I think it is Physical, mostly.") == "physical"
    assert PL.parse_guess("unsure") is None


def test_guesser_plumbing_and_blindness(tmp_path):
    res = PL.run(mock=True, gen_code="M1", out_dir=tmp_path, write=True)
    f = tmp_path / "panel_judge_visible_outputs.jsonl"
    part = PL.run_guesser(f, adapter=PL.FakeGuesser(), limit=12)
    assert part["reads_hidden_metadata"] is False and part["unblinded"] is False
    assert part["n_guesses"] + part["n_errors"] == 12


def test_guesser_refuses_non_blind(tmp_path):
    f = tmp_path / "jv.jsonl"
    f.write_text(json.dumps({"item_id": "b17-01", "target_text": "river", "neutral_context": "n",
                             "blinded_output_id": "L0001", "generation_text": "uses varna KCPR",
                             "output_format": "x"}) + "\n")
    with pytest.raises(ValueError):
        PL.run_guesser(f, adapter=PL.FakeGuesser())


def test_aggregate_controllability_accuracy():
    # perfect dial on VARNA arm, chance on PLAIN
    hidden = [
        {"blinded_output_id": "L1", "true_arm": "VARNA_SPHERE_LENS", "target_sphere": "mental"},
        {"blinded_output_id": "L2", "true_arm": "VARNA_SPHERE_LENS", "target_sphere": "physical"},
        {"blinded_output_id": "L3", "true_arm": "PLAIN_SPHERE_INSTRUCTION", "target_sphere": "spiritual"},
        {"blinded_output_id": "L4", "true_arm": "NO_LENS_BASELINE", "target_sphere": None},
    ]
    guesses = [{"blinded_output_id": "L1", "guess": "mental"},      # correct
               {"blinded_output_id": "L2", "guess": "physical"},    # correct
               {"blinded_output_id": "L3", "guess": "physical"},    # wrong
               {"blinded_output_id": "L4", "guess": "mental"}]      # ignored (no target)
    res = PL.aggregate_controllability(guesses, hidden)
    s = res["controllability_by_arm"]
    assert s["VARNA_SPHERE_LENS"]["accuracy"] == 1.0 and s["VARNA_SPHERE_LENS"]["n"] == 2
    assert s["PLAIN_SPHERE_INSTRUCTION"]["accuracy"] == 0.0
    assert "NO_LENS_BASELINE" not in s              # only lens arms scored
    assert res["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"


def test_no_genutility_label_anywhere():
    res = PL.run(mock=True)
    blob = json.dumps(res)
    assert not re.search(r"GENUTILITY_[A-Z]", blob)
    agg = PL.aggregate_controllability([], [])
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(agg))
