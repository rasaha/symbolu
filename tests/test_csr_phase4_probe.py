"""CPU tests for Phase 4 Stage-A plumbing — probe math (synthetic activations) + collector helpers.

No GPU, no torch, no model. Validates: the linear-probe / AUROC math, group-by-term CV (no term in
both splits), the dimension-matched random-feature control, Bhava-collapse detection, the leakage
check, bootstrap AUROC-delta CIs, decide_phase4 label logic, and the collector's metadata schema +
no-answer-token guarantee. This is Stage-A infrastructure only — NO Phase 4 claim is made.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

np = pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import phase4_probe as PB              # noqa: E402
from csr_match_filter import phase4_collect_states as PC     # noqa: E402
from csr_match_filter import phase4_probe_eval as PE         # noqa: E402


def _groups(n, n_terms, seed=0):
    return np.array([f"t{i % n_terms}" for i in range(n)])


# ---- AUROC + linear probe -----------------------------------------------------------------------

def test_auroc_basic_and_ties():
    assert PB.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert PB.auroc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert abs(PB.auroc([0, 1], [0.5, 0.5]) - 0.5) < 1e-9          # tie -> 0.5
    assert PB.auroc([1, 1], [0.3, 0.7]) == 0.5                     # one class -> 0.5


def test_probe_recovers_signal_under_group_cv():
    rng = np.random.default_rng(1)
    n, d = 240, 24
    X = rng.standard_normal((n, d))
    w = np.zeros(d); w[:4] = [3.0, -3.0, 3.0, -3.0]
    y = (X @ w + rng.standard_normal(n) * 0.5 > 0).astype(int)
    groups = _groups(n, 24)                                        # signal is feature-based, not term
    res = PB.evaluate_probe(X, y, groups, seed=0)
    assert res["auroc"] > 0.75


def test_probe_no_signal_is_chance():
    rng = np.random.default_rng(2)
    n, d = 200, 16
    X = rng.standard_normal((n, d))
    y = rng.integers(0, 2, n)
    auc = PB.evaluate_probe(X, y, _groups(n, 20), seed=0)["auroc"]
    assert 0.35 < auc < 0.65                                       # ~ chance


# ---- group-by-term CV -----------------------------------------------------------------------------

def test_group_kfold_has_no_term_leakage():
    groups = _groups(100, 10)
    for tr, te in PB.group_kfold_indices(groups, n_splits=5, seed=3):
        assert len(tr) and len(te)
        assert set(groups[tr].tolist()).isdisjoint(set(groups[te].tolist()))


# ---- collapse detection ---------------------------------------------------------------------------

def test_effective_rank_detects_collapse():
    rng = np.random.default_rng(4)
    n = 150
    collapsed = rng.standard_normal((n, 1)) @ rng.standard_normal((1, 12))   # rank 1
    full = rng.standard_normal((n, 12))
    assert PB.effective_rank(collapsed) < 1.5
    assert PB.effective_rank(full) > 8.0


# ---- dimension-matched control --------------------------------------------------------------------

def test_incremental_value_credits_real_extra_signal():
    rng = np.random.default_rng(5)
    n = 260
    X_hidden = rng.standard_normal((n, 16))                       # no signal in hidden
    X_extra = rng.standard_normal((n, 4))
    y = (X_extra @ np.array([3.0, -3.0, 3.0, -3.0]) + rng.standard_normal(n) * 0.5 > 0).astype(int)
    iv = PB.incremental_value(X_hidden, X_extra, y, _groups(n, 26), seed=0, n_boot=300)
    assert iv["auroc_hidden_extra"] > iv["auroc_hidden"] + 0.10
    assert iv["delta_vs_hidden"]["delta"] > 0 and iv["delta_vs_hidden"]["excludes_zero"]
    assert iv["delta_vs_random"]["delta"] > 0 and iv["delta_vs_random"]["excludes_zero"]


def test_incremental_value_noise_extra_adds_nothing_over_random():
    rng = np.random.default_rng(6)
    n = 260
    X_hidden = rng.standard_normal((n, 16))
    y = (X_hidden @ (np.r_[np.array([3.0, -3.0, 3.0]), np.zeros(13)])
         + rng.standard_normal(n) * 0.5 > 0).astype(int)          # signal is in hidden
    X_extra = rng.standard_normal((n, 4))                         # pure noise
    iv = PB.incremental_value(X_hidden, X_extra, y, _groups(n, 26), seed=0, n_boot=300)
    assert not iv["delta_vs_random"]["excludes_zero"]             # noise doesn't beat random


# ---- leakage check --------------------------------------------------------------------------------

def test_leakage_flag_on_near_perfect_extra():
    rng = np.random.default_rng(7)
    n = 200
    y = rng.integers(0, 2, n)
    leaky = np.c_[y + rng.standard_normal(n) * 0.01, rng.standard_normal(n)]   # col == label
    clean = rng.standard_normal((n, 4))
    assert PB.leakage_check(leaky, y, _groups(n, 20))["leakage_suspected"] is True
    assert PB.leakage_check(clean, y, _groups(n, 20))["leakage_suspected"] is False


def test_leakage_flag_on_supervision_confound():
    rng = np.random.default_rng(8)
    n = 200
    y = rng.integers(0, 2, n)
    out = PB.leakage_check(rng.standard_normal((n, 4)), y, _groups(n, 20), supervision=y)
    assert out["leakage_suspected"] is True                       # supervision == target


# ---- bootstrap CI ---------------------------------------------------------------------------------

def test_bootstrap_delta_ci():
    rng = np.random.default_rng(9)
    n = 200
    y = rng.integers(0, 2, n)
    good = y + rng.standard_normal(n) * 0.3
    bad = rng.standard_normal(n)
    d = PB.bootstrap_auroc_delta(y, good, bad, n_boot=400, seed=0)
    assert d["delta"] > 0 and d["excludes_zero"]
    same = PB.bootstrap_auroc_delta(y, bad, bad, n_boot=400, seed=0)
    assert not same["excludes_zero"]


# ---- decision labels ------------------------------------------------------------------------------

def _excl(delta):
    return {"delta": delta, "ci_low": delta - 0.01, "ci_high": delta + 0.01, "excludes_zero": delta > 0}


def test_decide_phase4_precedence_and_labels():
    d_pos, d_zero = _excl(0.08), {"delta": 0.0, "ci_low": -0.05, "ci_high": 0.05, "excludes_zero": False}
    # leakage dominates everything
    assert PB.decide_phase4(0.9, d_pos, d_pos, 10.0, leakage=True) == "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    # collapse next
    assert PB.decide_phase4(0.9, d_pos, d_pos, 1.2, leakage=False) == "PHASE4_BHAVA_COLLAPSE"
    # inconclusive
    assert PB.decide_phase4(0.9, d_pos, d_pos, 10.0, leakage=False, inconclusive=True) == \
        "PHASE4_PILOT_INCONCLUSIVE"
    # hidden not predictive
    assert PB.decide_phase4(0.52, d_pos, d_pos, 10.0, leakage=False) == "PHASE4_NOT_PREDICTIVE"
    # adds signal (beats hidden AND random, >= min_delta, CIs exclude 0)
    assert PB.decide_phase4(0.70, d_pos, d_pos, 10.0, leakage=False) == "PHASE4_BHAVA_ADDS_SIGNAL"
    # predictive but no added value
    assert PB.decide_phase4(0.70, d_zero, d_zero, 10.0, leakage=False) == \
        "PHASE4_HIDDEN_STATE_PREDICTIVE"


# ---- collector helpers (no GPU) -------------------------------------------------------------------

_FRAME = {"primary_domains": ["medicine"], "secondary_domains": ["care"],
          "rejected_domains": ["commerce"]}


class _Trace:
    primary_domains = ["medicine"]; secondary_domains = ["care"]; rejected_domains = ["commerce"]


def test_resolve_layers():
    assert PC.resolve_layers("all", 5) == [0, 1, 2, 3, 4]
    assert PC.resolve_layers("0,8,16", 33) == [0, 8, 16]


def test_build_prompts_uses_frozen_builders():
    ex = {"id": "x", "query": "What is a doctor?"}
    pr = PC.build_prompts(ex, _Trace())
    assert "medicine" in pr["framed"] and "commerce" in pr["framed"]      # frame injected
    assert "medicine" not in pr["base"] and "doctor" in pr["base"].lower()  # base is frame-free


def test_metadata_schema_and_no_answer_token_guarantee():
    ex = {"id": "ord_001", "query": "What is a doctor?", "category": "ordinary"}
    m = PC.build_metadata_row(0, ex, "framed", "PROMPT TEXT", "mistralai/Mistral-7B-Instruct-v0.3",
                              [0, 8, 16], {"audit_pass": True}, "phase2b_traces", feature_dim=4096)
    for k in ("row_index", "id", "arm", "model_id", "prompt_sha256", "token_position",
              "extraction_mode", "reads_answer_tokens", "features_from_answer_tokens", "layers",
              "label_source", "labels", "feature_dim"):
        assert k in m
    assert m["token_position"] == -1
    assert m["extraction_mode"] == "last_prompt_token_pre_generation"
    assert m["reads_answer_tokens"] is False and m["features_from_answer_tokens"] is False
    assert len(m["prompt_sha256"]) == 64


def test_labels_from_audit_maps_findings():
    compliant = "A doctor primarily involves medicine, clinical, and cure here."
    lab = PC.labels_from_audit("What is a doctor?", compliant, _FRAME, terms=["doctor"])
    assert lab["audit_pass"] and not lab["frame_violation"] and not lab["rejected_domain_leak"]
    leak = "A doctor is basically about business, market, and trade above all."
    lab2 = PC.labels_from_audit("What is a doctor?", leak, _FRAME, terms=["doctor"])
    assert lab2["audit_fail"] and lab2["rejected_domain_leak"] and lab2["frame_violation"]


# ---- diagnostics: manifest / metadata / shape / labels / leakage / dry-run ----------------------

def _good_manifest():
    return {k: v for k, v in {
        "model_id": "m", "tokenizer_name": "m", "n_examples": 2, "arms": ["base", "framed"],
        "n_layers": 3, "d_model": 8, "layers": [0, 1, 2],
        "extraction_mode": PC.EXTRACTION_MODE, "token_position": -1,
        "token_position_desc": "final_prompt_token", "features_from_answer_tokens": False,
        "reads_answer_tokens": False, "feature_provenance": "residual_stream_hidden_state",
        "contains_phase1_csr_scores": False, "contains_phonemic_12d_profile": False,
        "contains_csr_trace_vector": False, "prompt_hashes_present": 2, "trace_source": "none",
        "label_sources": ["none"], "skipped_examples": 0, "dry_run": False,
        "activations_synthetic": False, "valid_for_phase4_signal": True}.items()}


def test_manifest_schema_has_all_required_fields():
    assert PC.validate_manifest(_good_manifest()) == []
    bad = _good_manifest(); del bad["d_model"]
    assert "d_model" in PC.validate_manifest(bad)


def test_metadata_has_token_position_fields():
    ex = {"id": "x", "query": "What is a doctor?", "category": "ordinary"}
    m = PC.build_metadata_row(0, ex, "framed", "PROMPT", "model", [0, 8, 16],
                              {"audit_pass": True}, "phase2b_traces", feature_dim=4096,
                              prompt_token_count=42, final_prompt_token_id=733,
                              final_prompt_token_text="]", frame_summary={"primary": ["medicine"]},
                              answer_trace_source_id="x")
    assert m["prompt_token_count"] == 42 and m["final_prompt_token_id"] == 733
    assert m["final_prompt_token_text"] == "]" and m["token_position"] == -1
    assert m["prompt_hash"] == m["prompt_sha256"] and len(m["prompt_hash"]) == 64
    assert m["csr_frame_summary"] == {"primary": ["medicine"]}
    assert m["answer_trace_source_id"] == "x"
    assert m["feature_provenance"] == "residual_stream_hidden_state"


def test_shape_validation_catches_mismatched_n(tmp_path):
    p = tmp_path / "a.npz"
    X = np.random.default_rng(0).standard_normal((4, 3, 8)).astype("float32")
    np.savez_compressed(p, X=X, layers=np.array([0, 1, 2]),
                        ids=np.array(["a", "b", "c"], dtype=object),     # len 3 != N 4
                        arms=np.array(["base"] * 4, dtype=object))
    chk = PC.validate_saved_activations(p, expected_n_layers=3)
    assert chk["ok"] is False and any("len(ids)==N" in i for i in chk["issues"])


def test_shape_validation_flags_nan_and_zero_variance(tmp_path):
    p = tmp_path / "z.npz"
    X = np.zeros((5, 3, 8), dtype="float32")                              # zero variance
    np.savez_compressed(p, X=X, layers=np.array([0, 1, 2]),
                        ids=np.array(["a"] * 5, dtype=object), arms=np.array(["base"] * 5, dtype=object))
    chk = PC.validate_saved_activations(p, expected_n_layers=3)
    assert chk["ok"] is False and any("variance" in i for i in chk["issues"])


def test_label_balance_warning_below_threshold():
    meta = [{"labels": {k: (i < 3 and k == "audit_fail") for k in PC.DIAG_LABELS}}
            for i in range(20)]
    diag = PC.label_diagnostics(meta, min_pos=5)
    assert diag["balance"]["audit_fail"]["pos"] == 3
    assert any("audit_fail" in w for w in diag["warnings"])
    # missing labels counted
    diag2 = PC.label_diagnostics([{"labels": None}, {"labels": {k: True for k in PC.DIAG_LABELS}}],
                                 min_pos=1)
    assert diag2["n_missing_labels"] == 1


def test_leakage_assertions_pass_and_fail():
    ok = PC.assert_no_feature_leakage(_good_manifest(), [PC.build_metadata_row(
        0, {"id": "x", "query": "q"}, "base", "p", "m", [0], None, "none")])
    assert ok["ok"] and not ok["problems"]
    assert ok["answer_tokens_used_as_features"] is False
    assert ok["phonemic_12d_in_features"] is False and ok["csr_trace_vector_in_features"] is False
    bad = _good_manifest(); bad["contains_phonemic_12d_profile"] = True
    res = PC.assert_no_feature_leakage(bad, [])
    assert res["ok"] is False and any("phonemic_12d" in p for p in res["problems"])


# ---- Stage-B primitives: PCA + single-AUROC CI ---------------------------------------------------

def test_pca_fit_transform_shapes_and_infold():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((40, 50))
    p = PB.pca_fit(X[:30], 8)
    assert p["comps"].shape == (8, 50)
    assert PB.pca_transform(p, X[30:]).shape == (10, 8)


def test_cv_oof_with_pca_recovers_signal():
    rng = np.random.default_rng(1)
    n, d = 220, 80
    X = rng.standard_normal((n, d))
    w = np.zeros(d); w[:4] = [4, -4, 4, -4]
    y = (X @ w + rng.standard_normal(n) * 0.5 > 0).astype(int)
    auc = PB.evaluate_probe(X, y, _groups(n, 22), n_pca=32, seed=0)["auroc"]
    assert auc > 0.75


def test_bootstrap_auroc_ci_above_chance():
    rng = np.random.default_rng(2)
    n = 200
    y = rng.integers(0, 2, n)
    good = y + rng.standard_normal(n) * 0.3
    ci = PB.bootstrap_auroc_ci(y, good, n_boot=400, seed=0)
    assert ci["above_chance"] and ci["ci_low"] > 0.5
    noise = PB.bootstrap_auroc_ci(y, rng.standard_normal(n), n_boot=400, seed=0)
    assert not noise["above_chance"]


# ---- Stage-B driver (synthetic activations) ------------------------------------------------------

def _write_synthetic_run(tmp_path, n_terms=40, planted_layer=2, signal=True, seed=0):
    """Build a tiny phase4 run dir: 2 layers of noise + 1 planted layer carrying audit_fail signal."""
    rng = np.random.default_rng(seed)
    rows, Xs = [], []
    layers = [0, 1, 2, 3]
    D = 40
    for t in range(n_terms):
        for arm in ("base", "framed"):
            y = int(rng.integers(0, 2))
            cube = rng.standard_normal((len(layers), D))
            if signal:
                cube[planted_layer, :4] += (3.0 if y else -3.0)     # planted in one layer
            term = f"wd{chr(97 + t // 26)}{chr(97 + t % 26)}qx"     # distinct alphabetic term per t
            rows.append({"id": f"trm_{t}", "arm": arm, "query": term,
                         "labels": {"audit_fail": bool(y), "frame_violation": bool(y),
                                    "rejected_domain_leak": False, "secondary_promoted": False}})
            Xs.append(cube)
    X = np.stack(Xs, 0)
    rd = tmp_path / "csr_phase4"
    rd.mkdir(parents=True)
    np.savez_compressed(rd / "phase4_activations.npz", X=X.astype("float32"),
                        layers=np.array(layers), ids=np.array([r["id"] for r in rows], dtype=object),
                        arms=np.array([r["arm"] for r in rows], dtype=object))
    (rd / "phase4_metadata.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    return rd


def test_driver_groups_by_term_and_loads(tmp_path):
    import json as _json  # noqa
    rd = _write_synthetic_run(tmp_path)
    X, layers, arms, rows = PE.load_run(rd)
    assert X.ndim == 3 and len(layers) == 4 and len(arms) == len(rows)
    groups = PE.groups_for(rows)
    # base+framed of the same term share a group
    assert groups[0] == groups[1]


def test_driver_detects_signal_and_writes_outputs(tmp_path):
    rd = _write_synthetic_run(tmp_path, signal=True)
    rep = PE.run(rd, ["audit_fail"], [], "all", n_pca=8, n_splits=4, n_boot=200, seed=0, min_pos=10)
    t = rep["targets"]["audit_fail"]
    # planted within-arm signal -> predictive (per-arm CI above chance)
    assert t["decision"] == "PHASE4_HIDDEN_STATE_PREDICTIVE"
    assert t["units"]["framed"]["sufficient"] and t["units"]["framed"]["ci_low"] > 0.5
    md = PE.to_markdown(rep)
    assert "audit_fail" in md and "PHASE4_HIDDEN_STATE_PREDICTIVE" in md


def test_driver_no_signal_not_predictive(tmp_path):
    rd = _write_synthetic_run(tmp_path, signal=False)
    rep = PE.run(rd, ["audit_fail"], [], "all", n_pca=8, n_splits=4, n_boot=200, seed=0, min_pos=10)
    assert rep["targets"]["audit_fail"]["decision"] in ("PHASE4_NOT_PREDICTIVE",)


def test_driver_insufficient_label_power(tmp_path):
    rd = _write_synthetic_run(tmp_path)
    # rejected_domain_leak is all-False in the fixture -> 0 positives -> insufficient
    rep = PE.run(rd, [], ["rejected_domain_leak"], "all", n_pca=8, n_splits=4, n_boot=100, seed=0,
                 min_pos=10)
    assert rep["targets"]["rejected_domain_leak"]["decision"] == "PHASE4_INSUFFICIENT_LABEL_POWER"


def test_driver_decision_label_set():
    assert set(PE.DECISIONS) == {"PHASE4_HIDDEN_STATE_PREDICTIVE", "PHASE4_NOT_PREDICTIVE",
                                 "PHASE4_INSUFFICIENT_LABEL_POWER", "PHASE4_LEAKAGE_SUSPECTED"}


def test_dry_run_marked_non_valid(tmp_path, monkeypatch):
    import json as _json
    monkeypatch.setattr(sys, "argv",
                        ["prog", "--dry-run", "--limit", "2", "--arms", "base,framed",
                         "--out-dir", str(tmp_path)])
    PC.main()
    man = _json.loads((tmp_path / "phase4_manifest.json").read_text())
    assert man["dry_run"] is True and man["activations_synthetic"] is True
    assert man["valid_for_phase4_signal"] is False
    assert man["manifest_complete"] is True and man["leakage_diagnostics"]["ok"] is True
    assert man["features_from_answer_tokens"] is False
