#!/usr/bin/env python3
"""Mock tests for the B1.4b′ screening-run driver. NO real McRae data, NO real evidence run,
NO evidence freeze. Builds a self-contained synthetic mock env (temp source + private Y +
manifest + declaration) to exercise the freeze gate, and uses synthetic arm scores / synthetic
Y to prove screening cannot emit a positive and that every allowed label is reachable.

    python3 test_run_b1_4b_prime_screening.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run_b1_4b_prime_screening as R
import b1_4b_prime_scorer as S
import b1_4b_prime_prepare_mcrae_y as PREP

WORDS = ["cat", "dog", "pen", "cup", "bag", "mat", "lamp", "desk", "fork", "sock",
         "barn", "bench", "lemon", "spinach", "apron", "canoe", "cushion", "table",
         "bed", "bowl", "box", "basket", "kite", "drum", "ring", "nail", "rope",
         "vase", "clip", "mug", "tent", "boot", "coin", "leaf", "star", "sled",
         "brick", "plank", "spoon", "candle"]


def _mock_env(td: pathlib.Path, y_regime="null", declare=True, mode="screening",
              tamper_manifest=False, tamper_y=False):
    src = td / "src"; priv = td / "priv"; src.mkdir(); priv.mkdir()
    concepts = sorted(WORDS)
    n = len(concepts)
    rng = np.random.default_rng(0)
    m = 6
    if y_regime == "null":
        Y = (rng.random((n, m)) < 0.3).astype(np.int8)
    else:
        Y = (rng.random((n, m)) < 0.3).astype(np.int8)
    # synthetic source files with the canonical names + a KF column for build_records
    (src / "CONCS_brm.txt").write_text("Concept\tKF\n" + "\n".join(f"{c}\t{i+1}" for i, c in enumerate(concepts)) + "\n")
    (src / "CONCS_FEATS_concstats_brm.txt").write_text("Concept\tFeature\tProd_Freq\tBR_Label\n")
    (src / "FEATS_brm.txt").write_text("Feature\n")
    (src / "READ_ME.txt").write_text("mock\n")
    (src / "ReadMe_Terms_of_Use.txt").write_text("mock terms\n")
    # private Y npz
    if tamper_y:
        Yw = Y.copy(); Yw[0, 0] ^= 1
    else:
        Yw = Y
    np.savez_compressed(priv / "mcrae_y_matrix.npz", Y=Yw,
                        concepts=np.array(concepts), features=np.array([f"f{j}" for j in range(m)]))
    # manifest with hashes computed the SAME way as prep (against the UN-tampered Y)
    c_sha = PREP._sha_text("\n".join(concepts))
    f_sha = PREP._sha_text("\n".join([f"f{j}" for j in range(m)]))
    y_sha = PREP._sha_bytes(Y.tobytes() + c_sha.encode() + f_sha.encode())
    manifest = {
        "artifact": "mock_manifest",
        "private_source_file_sha256": {name: PREP._sha_file(src / name) for name in
            ("CONCS_brm.txt", "CONCS_FEATS_concstats_brm.txt", "FEATS_brm.txt",
             "READ_ME.txt", "ReadMe_Terms_of_Use.txt")},
        "y_matrix_sha256": y_sha,
    }
    man_path = priv / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2))
    man_sha = PREP._sha_file(man_path)
    if tamper_manifest:
        man_sha = "0" * 64
    decl_path = priv / R.DECL_NAME
    if declare:
        decl_path.write_text(json.dumps({
            "artifact": "b1_4b_prime_EVIDENCE_FREEZE_DECLARED",
            "evidence_freeze_declared": True, "mode": mode,
            "manifest_sha256": man_sha, "declared_by": "mock", "attestation": "mock screening"}))
    return src, priv, man_path, decl_path


# ---- freeze-gate refusals ----
def test_refuses_without_declaration():
    with tempfile.TemporaryDirectory() as d:
        src, priv, man, decl = _mock_env(pathlib.Path(d), declare=False)
        try:
            R.run_screening(src, priv, man, decl); raise AssertionError("did not refuse")
        except SystemExit as e:
            assert "REFUSED" in str(e) and "no EVIDENCE_FREEZE_DECLARED" in str(e)


def test_refuses_on_manifest_mismatch():
    with tempfile.TemporaryDirectory() as d:
        src, priv, man, decl = _mock_env(pathlib.Path(d), tamper_manifest=True)
        try:
            R.run_screening(src, priv, man, decl); raise AssertionError("did not refuse")
        except SystemExit as e:
            assert "manifest hash mismatch" in str(e)


def test_refuses_on_private_y_hash_mismatch():
    with tempfile.TemporaryDirectory() as d:
        src, priv, man, decl = _mock_env(pathlib.Path(d), tamper_y=True)
        try:
            R.run_screening(src, priv, man, decl); raise AssertionError("did not refuse")
        except SystemExit as e:
            assert "private Y hash mismatch" in str(e)


def test_refuses_wrong_mode():
    with tempfile.TemporaryDirectory() as d:
        src, priv, man, decl = _mock_env(pathlib.Path(d), mode="full")
        try:
            R.run_screening(src, priv, man, decl); raise AssertionError("did not refuse")
        except SystemExit as e:
            assert "mode" in str(e)


# ---- gated mock run succeeds + report properties ----
def test_gated_mock_run_produces_allowed_label_and_clean_report():
    with tempfile.TemporaryDirectory() as d:
        src, priv, man, decl = _mock_env(pathlib.Path(d))
        rep = R.run_screening(src, priv, man, decl, out_path=str(pathlib.Path(d) / "report.json"))
        assert rep["terminal_label"] in R.SCREENING_ALLOWED
        assert rep["terminal_label"] not in R.FORBIDDEN_IN_SCREENING
        # H pending visible; report has no raw feature values
        assert "H_SENTIMENT_LEXICON" in rep["pending_arms"]
        txt = json.dumps(rep)
        assert "Prod_Freq" not in txt and rep["raw_mcrae_data_in_report"] is False
        assert rep["mode"] == "screening"


# ---- screening disables SIGNAL ----
def test_screening_cannot_emit_signal_from_scores():
    m, ch = S.MARGIN, S.CHANCE
    hi = ch + 3 * m; lo = 0.05
    base = {x: lo for x in ("B_PHONOLOGY_PLAIN", "C_PHONOLOGY_SIMILARITY", "D_BAG_OF_PHONEMES",
                            "E_SHUFFLED_ORDER_F3", "F_RANDOM_RELABEL_F3", "G_LENGTH_FREQUENCY",
                            "I_NULL_CHANCE")}
    lab = R.screening_decide({"A_F3_REAL": hi, **base})
    assert lab == R.POSITIVE_SCREENING_LABEL
    assert lab not in R.FORBIDDEN_IN_SCREENING


def test_screening_f3_regime_maps_to_positive_needs_baselines():
    # synthetic F-3-winning data -> full scorer would say SIGNAL; screening must downgrade it
    recs, Y = S.make_synthetic("f3")
    arm_scores, _ = S.score_arms(recs, Y)
    assert S.decide_label_arms(arm_scores) == "L1_L2_L3_ATTRIBUTE_SIGNAL"     # underlying
    assert R.screening_decide(arm_scores) == R.POSITIVE_SCREENING_LABEL       # screening downgrade


def test_each_allowed_screening_label_reachable():
    # from real machinery on synthetic regimes:
    got = set()
    for regime in ("f3", "phonology", "bag", "null"):
        recs, Y = S.make_synthetic(regime)
        got.add(R.screening_decide(*[S.score_arms(recs, Y)[0]]))
    assert R.POSITIVE_SCREENING_LABEL in got            # f3
    assert "F_COLLAPSES_TO_PHONOLOGY" in got            # phonology
    assert "BAG_OR_SHUFFLE_EXPLAINS" in got             # bag
    assert "NULL_RETURN_BOTTOM" in got                  # null
    # remaining via injected arm scores:
    m, ch = S.MARGIN, S.CHANCE; hi = ch + 3 * m; lo = 0.05
    base = {x: lo for x in ("B_PHONOLOGY_PLAIN", "C_PHONOLOGY_SIMILARITY", "D_BAG_OF_PHONEMES",
                            "E_SHUFFLED_ORDER_F3", "F_RANDOM_RELABEL_F3", "G_LENGTH_FREQUENCY", "I_NULL_CHANCE")}
    assert R.screening_decide({"A_F3_REAL": hi, **{**base, "F_RANDOM_RELABEL_F3": hi}}) == "RANDOM_RELABEL_EXPLAINS"
    inc = {"A_F3_REAL": 0.48, "B_PHONOLOGY_PLAIN": 0.34, "C_PHONOLOGY_SIMILARITY": 0.33,
           "D_BAG_OF_PHONEMES": 0.30, "E_SHUFFLED_ORDER_F3": 0.29, "F_RANDOM_RELABEL_F3": 0.28,
           "G_LENGTH_FREQUENCY": 0.25, "I_NULL_CHANCE": 0.20}
    assert R.screening_decide(inc) == "INCONCLUSIVE"
    assert R.screening_decide({"A_F3_REAL": hi, **base}, {"y_not_independent": True}) == "Y_NOT_INDEPENDENT"
    assert R.screening_decide({"A_F3_REAL": hi, **base}, {"decoder_leak": True}) == "DECODER_LEAKAGE_INVALID"


# ---- Terms / hygiene guards ----
def test_no_raw_mcrae_or_private_y_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
    for pat in ("CONCS_brm", "CONCS_FEATS", "FEATS_brm", "cos_matrix", "mcrae_y_matrix",
                "private_mcrae", "EVIDENCE_FREEZE_DECLARED"):
        assert not [t for t in tracked if pat in pathlib.Path(t).name], pat


def test_driver_reads_no_committed_real_data():
    src = (HERE / "run_b1_4b_prime_screening.py").read_text()
    # the driver must not hardcode reading a committed real Y / raw file
    assert "CONCS_brm" not in src or "resolve" in src   # only via resolver on a supplied source dir


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed  (MOCK ONLY — no real run, no evidence freeze)")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
